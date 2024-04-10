import logging, os, requests, time, sys
from pystackql import StackQL

# get environment variables
slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
repo = os.getenv("GITHUB_REPO")
owner = os.getenv("GITHUB_REPO_OWNER")
formula_name = os.getenv("HOMEBREW_FORMULA_NAME")
sleep_interval = os.getenv("SLEEP_INTERVAL")
backend_file_storage_location = os.getenv("BACKEND_FILE_STORAGE_LOCATION", "stackql.db")

# set up logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, log_level, None)
if not isinstance(numeric_level, int):
    raise ValueError(f"Invalid log level: {log_level}")
        
logging.basicConfig(level=numeric_level,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# instantiate StackQL - use stackql binary in container, maintain durable state for materialized views
stackql = StackQL(download_dir="/srv/stackql", backend_storage_mode="file", backend_file_storage_location=backend_file_storage_location)

def run_stackql_stmt(stmt):
    try:
        msg = stackql.executeStmt(stmt)
        logger.info(msg[0]["message"].strip())
    except Exception as e:
        logger.error(f"❌ error in run_stackql_stmt: {e}")

def send_to_slack(message, icon_emoji):
    try:
        payload = {
            "text": message,
            "username": "slackbot",
            "icon_emoji": icon_emoji,
            "mrkdwn": True
        }
        requests.post(slack_webhook_url, json=payload)
    except Exception as e:
        logger.error(f"❌ error in send_to_slack: {e}")

def send_to_discord(message):
    try:
        payload = {
            "content": message
        }
        requests.post(discord_webhook_url, json=payload)
    except Exception as e:
        logger.error(f"❌ Error in send_to_discord: {e}")

def send_notification(message, slack_icon_emoji=":chart_with_upwards_trend:"):
    # send to slack if webhook URL is set
    send_to_slack(message, slack_icon_emoji) if len(slack_webhook_url) > 0 else logger.debug("no slack webhook URL found. skipping...")
    # send to discord if webhook URL is set
    send_to_discord(message) if len(discord_webhook_url) > 0 else logger.debug("no discord webhook URL found. skipping...")
    logger.info(message.replace("\n", " "))

def main():
    logger.info("🚀 starting oss-activity-monitor...")
    logger.info(f"stackql version: {stackql.version}")
    logger.info(f"pystackql version: {stackql.package_version}")
    
    # pull providers
    logger.info("pulling required providers from StackQL registry")
    providers = ["github", "homebrew"]
    for provider in providers:
        run_stackql_stmt(f"REGISTRY PULL {provider}")

    # 
    # create materialized views
    #

    # github repo stargazers
    logger.info(f"⭐ initializing materialized view for repo stargazers for {owner}/{repo}...")

    mat_view_query = """
CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_stargazers AS 
SELECT login FROM github.activity.repo_stargazers
WHERE owner = '%s' and repo = '%s'
""" % (owner, repo)

    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_stargazers")[0]["count"]
    logger.info(f"⭐ found {init_count} initial repo stargazers for {owner}/{repo}")

    # github repo watchers
    logger.info(f"👀 initializing materialized view for repo watchers for {owner}/{repo}...")

    mat_view_query = """
CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_watchers AS 
SELECT login FROM github.activity.repo_watchers 
WHERE owner = '%s' and repo = '%s'
""" % (owner, repo)

    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_watchers")[0]["count"]
    logger.info(f"👀 found {init_count} initial repo watchers for {owner}/{repo}")

    # github repo forks
    logger.info(f"🍴 initializing materialized view for repo forks for {owner}/{repo}...")

    mat_view_query = """
CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_forks AS 
SELECT JSON_EXTRACT(owner, '$.login') AS login FROM github.repos.forks 
WHERE owner = '%s' and repo = '%s'
""" % (owner, repo)

    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_forks")[0]["count"]
    logger.info(f"🍴 found {init_count} initial repo forks for {owner}/{repo}")

    # github repo issues
    logger.info(f"📊 initializing materialized view for repo issues for {owner}/{repo}...")

    mat_view_query = """
CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_issues AS 
SELECT id, json_extract(user, '$.login') as reporter
FROM github.issues.issues
WHERE owner = '%s' and repo = '%s'
""" % (owner, repo)

    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_issues")[0]["count"]
    logger.info(f"📊 found {init_count} initial repo issues for {owner}/{repo}")

    # github org followers
    logger.info(f"🙋 initializing materialized view for org followers for {owner}...")

    mat_view_query = """
CREATE OR REPLACE MATERIALIZED VIEW mvw_github_org_followers AS 
SELECT login FROM github.users.followers WHERE username = '%s'
""" % (owner)
    
    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_org_followers")[0]["count"]
    logger.info(f"🙋 found {init_count} initial org followers for {owner}")

    # github release assset downloads
    logger.info(f"📦 initializing materialized view for release asset downloads for {owner}/{repo}...")

    mat_view_query = """
CREATE OR REPLACE MATERIALIZED VIEW mvw_github_release_asset_downloads AS 
SELECT
SPLIT_PART(JSON_EXTRACT(json_each.value, '$.browser_download_url'), '/', -1) as asset_name,
SUM(JSON_EXTRACT(json_each.value, '$.download_count')) as download_count
FROM github.repos.releases, json_each(assets)
WHERE owner = '%s' AND repo = '%s'
GROUP BY asset_name
""" % (owner, repo)

    run_stackql_stmt(mat_view_query)
    asset_downloads = stackql.execute("SELECT asset_name, download_count FROM mvw_github_release_asset_downloads")
    for asset in asset_downloads:
        logger.info(f"📦 found {asset['download_count']} initial downloads for {asset['asset_name']}")

    # homebrew downloads
    logger.info(f"🍺 initializing materialized view for homebrew downloads for {formula_name}...")
    
    mat_view_query = """
CREATE OR REPLACE MATERIALIZED VIEW mvw_homebrew_downloads AS 
SELECT
JSON_EXTRACT(analytics, '$.install.30d.%s') as installs_30d,
JSON_EXTRACT(analytics, '$.install.90d.%s') as installs_90d,
JSON_EXTRACT(analytics, '$.install.365d.%s') as installs_365d
FROM homebrew.formula.formula
WHERE formula_name = '%s'
""" % (formula_name, formula_name, formula_name, formula_name)
    
    run_stackql_stmt(mat_view_query)
    init_count_30d = stackql.execute("SELECT installs_30d FROM mvw_homebrew_downloads")[0]["installs_30d"]
    logger.info(f"🍺 found {init_count_30d} initial 30d downloads for {formula_name}")
    init_count_90d = stackql.execute("SELECT installs_90d FROM mvw_homebrew_downloads")[0]["installs_90d"]
    logger.info(f"🍺 found {init_count_90d} initial 90d downloads for {formula_name}")
    init_count_365d = stackql.execute("SELECT installs_365d FROM mvw_homebrew_downloads")[0]["installs_365d"]
    logger.info(f"🍺 found {init_count_365d} initial 365d downloads for {formula_name}")        

    logger.info("🚀 starting monitoring loop...")
    try:
        while True:
            #
            # find new stargazers
            #
            logger.debug("checking for new stargazers...")

            left_join_query = """
SELECT c.login
FROM github.activity.repo_stargazers c
LEFT JOIN mvw_github_repo_stargazers mvw
ON c.login = mvw.login
WHERE mvw.login IS NULL
AND c.owner = '%s' AND c.repo = '%s'
""" % (owner, repo)

            new_stargazers = stackql.execute(left_join_query)
            # refresh state
            stackql.executeStmt("REFRESH MATERIALIZED VIEW mvw_github_repo_stargazers")
            # get overall total stargazers
            total_stargazers = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_stargazers")[0]["count"]
            logger.debug(f"total stargazers : {total_stargazers}")
            # send notification
            if new_stargazers:
                message = f"⭐ {len(new_stargazers)} new repo {'stargazer' if len(new_stargazers) == 1 else 'stargazers'} for {owner}/{repo} ({', '.join([stargazer['login'] for stargazer in new_stargazers])})\ntotal stargazers : {total_stargazers}"
                send_notification(message)
            else: 
                logger.debug("no new stargazers found")

            #
            # find repo watchers
            #        
            logger.debug("checking for new repo watchers...")

            left_join_query = """
SELECT c.login
FROM github.activity.repo_watchers c
LEFT JOIN mvw_github_repo_watchers mvw
ON c.login = mvw.login
WHERE mvw.login IS NULL
AND c.owner = '%s' AND c.repo = '%s'
""" % (owner, repo)

            new_repo_watchers = stackql.execute(left_join_query)
            # refresh state
            stackql.executeStmt("REFRESH MATERIALIZED VIEW mvw_github_repo_watchers")
            # get new total repo watchers
            total_repo_watchers = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_watchers")[0]["count"]
            logger.debug(f"total repo watchers : {total_repo_watchers}")
            # send notification
            if new_repo_watchers:
                message = f"👀 {len(new_repo_watchers)} new repo {'watcher' if len(new_repo_watchers) == 1 else 'watchers'} for {owner}/{repo} ({', '.join([watcher['login'] for watcher in new_repo_watchers])})\ntotal repo watchers : {total_repo_watchers}"
                send_notification(message)
            else: 
                logger.debug("no new repo watchers found")

            #
            # find new repo forks
            #
            logger.debug("checking for new repo forks...")

            left_join_query = """
SELECT json_extract(c.owner, '$.login') as login
FROM github.repos.forks c
LEFT JOIN mvw_github_repo_forks mvw
ON json_extract(c.owner, '$.login') = mvw.login
WHERE mvw.login IS NULL
AND c.owner = '%s' AND c.repo = '%s'       
""" % (owner, repo)

            new_repo_forks = stackql.execute(left_join_query)
            # refresh state
            stackql.executeStmt("REFRESH MATERIALIZED VIEW mvw_github_repo_forks")
            # get new total repo forks
            total_repo_forks = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_forks")[0]["count"]
            logger.debug(f"total repo forks : {total_repo_forks}")
            # send notification
            if new_repo_forks:
                message = f"🍴 {len(new_repo_forks)} new repo {'fork' if len(new_repo_forks) == 1 else 'forks'} for {owner}/{repo} ({', '.join([fork['login'] for fork in new_repo_forks])})\ntotal repo forks : {total_repo_forks}"
                send_notification(message)
            else:
                logger.debug("no new repo forks found")

            #
            # find new repo issues
            #
            logger.debug("checking for new repo issues...")

            left_join_query = """
SELECT c.id, json_extract(c.user, '$.login') as reporter
FROM github.issues.issues c
LEFT JOIN mvw_github_repo_issues mvw
ON c.id = mvw.id
WHERE mvw.id IS NULL
AND c.owner = '%s' AND c.repo = '%s'
""" % (owner, repo)

            new_repo_issues = stackql.execute(left_join_query)
            # refresh state
            stackql.executeStmt("REFRESH MATERIALIZED VIEW mvw_github_repo_issues")
            # get new total repo issues
            total_repo_issues = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_issues")[0]["count"]
            logger.debug(f"total repo issues : {total_repo_issues}")
            # send notification
            if new_repo_issues:
                reporters = ', '.join([issue['reporter'] for issue in new_repo_issues])
                message = f"📊 {len(new_repo_issues)} new repo {'issue' if len(new_repo_issues) == 1 else 'issues'} for {owner}/{repo} (raised by {reporters})\ntotal repo issues : {total_repo_issues}"
                send_notification(message)
            else:
                logger.debug("no new repo issues found")

            #
            # find new org followers
            #
            logger.debug("checking for new org followers...")

            left_join_query = """
SELECT c.login
FROM github.users.followers c
LEFT JOIN mvw_github_org_followers mvw
ON c.login = mvw.login
WHERE mvw.login IS NULL
AND c.username = '%s'
""" % (owner)

            new_org_followers = stackql.execute(left_join_query)
            # refresh state
            stackql.executeStmt("REFRESH MATERIALIZED VIEW mvw_github_org_followers")
            # get new total org followers
            total_org_followers = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_org_followers")[0]["count"]
            logger.debug(f"total org followers : {total_org_followers}")
            # send notification
            if new_org_followers:
                message = f"🙋 {len(new_org_followers)} new org {'follower' if len(new_org_followers) == 1 else 'followers'} for {owner} ({', '.join([follower['login'] for follower in new_org_followers])})\ntotal org followers : {total_org_followers}"
                send_notification(message)
            else:
                logger.debug("no new org followers found")

            #
            # find new release asset downloads
            #
            logger.debug("checking for new release asset downloads...")

            # create temp view for current downloads
            current_query = """
CREATE OR REPLACE MATERIALIZED VIEW tmp_current_github_release_asset_downloads AS 
SELECT
SPLIT_PART(JSON_EXTRACT(json_each.value, '$.browser_download_url'), '/', -1) as asset_name,
SUM(JSON_EXTRACT(json_each.value, '$.download_count')) as download_count
FROM github.repos.releases, json_each(assets)
WHERE owner = '%s' AND repo = '%s'
GROUP BY asset_name
""" % (owner, repo)

            stackql.executeStmt(current_query)

            # find the difference in downloads
            diff_query = """
SELECT c.asset_name,
(c.download_count - mvw.download_count) as new_downloads
FROM tmp_current_github_release_asset_downloads c
INNER JOIN mvw_github_release_asset_downloads mvw
ON c.asset_name = mvw.asset_name
"""

            total_new_downloads_query = """
SELECT SUM(new_downloads) FROM (
%s) t
""" % diff_query

            total_new_downloads = stackql.execute(total_new_downloads_query)
            logger.debug(f"total new downloads : {total_new_downloads[0]['new_downloads']}")
            if int(total_new_downloads[0]["new_downloads"]) > 0:
                # we have some new downloads
                asset_downloads = stackql.execute(diff_query)
                for asset in asset_downloads:
                    if int(asset["new_downloads"]) > 0:
                        send_notification(f"📦 {asset['new_downloads']} new GitHub release {'download' if int(asset['new_downloads']) == 1 else 'downloads'} for {asset['asset_name']}")
            # refresh state
            stackql.executeStmt("REFRESH MATERIALIZED VIEW mvw_github_release_asset_downloads")

            #
            # find new homebrew downloads
            #
            logger.debug("checking for new homebrew downloads...")

            # create temporary materialized view for current downloads
            current_query = """
CREATE OR REPLACE MATERIALIZED VIEW tmp_current_homebrew_downloads AS 
SELECT
JSON_EXTRACT(analytics, '$.install.30d.%s') as installs_30d,
JSON_EXTRACT(analytics, '$.install.90d.%s') as installs_90d,
JSON_EXTRACT(analytics, '$.install.365d.%s') as installs_365d
FROM homebrew.formula.formula
WHERE formula_name = '%s'
""" % (formula_name, formula_name, formula_name, formula_name)
            
            stackql.executeStmt(current_query)

            # find new downloads
            new_downloads_query = """
SELECT 
max((c.installs_30d - mvw.installs_30d),(c.installs_90d - mvw.installs_90d),(c.installs_365d - mvw.installs_365d)) as new_downloads
FROM tmp_current_homebrew_downloads c
JOIN mvw_homebrew_downloads mvw
ON 1=1
"""
            new_downloads = stackql.execute(new_downloads_query)
            logger.debug(f"new homebrew downloads : {new_downloads[0]['new_downloads']}")
            if int(new_downloads[0]["new_downloads"]) > 0:
                    message = f"🍺 {new_downloads[0]['new_downloads']} new homebrew {'download' if int(new_downloads[0]['new_downloads']) == 1 else 'downloads'} for {formula_name}"
                    send_notification(message)
            else:
                logger.debug("no new homebrew downloads found")
            # refresh state
            stackql.executeStmt("REFRESH MATERIALIZED VIEW mvw_homebrew_downloads")

            # sleep for sleep_interval secs
            logger.debug(f"sleeping for {sleep_interval} secs...")
            time.sleep(int(sleep_interval))

            pass
    except KeyboardInterrupt:
        print("Program terminated by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()