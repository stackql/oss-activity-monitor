import logging, os, requests
from pystackql import StackQL

# get environment variables
slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
repo = os.getenv('GITHUB_REPO')
owner = os.getenv('GITHUB_REPO_OWNER')
formula_name = os.getenv('HOMEBREW_FORMULA_NAME')

# set up logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
numeric_level = getattr(logging, log_level, None)
if not isinstance(numeric_level, int):
    raise ValueError(f'Invalid log level: {log_level}')
        
logging.basicConfig(level=numeric_level,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# instantiate StackQL
stackql = StackQL(backend_storage_mode='file')

def run_stackql_stmt(stmt):
    try:
        msg = stackql.executeStmt(stmt)
        logger.info(msg[0]['message'].strip())
    except Exception as e:
        logger.error(f"❌ error in run_stackql_stmt: {e}")

def send_to_slack(message, icon_emoji):
    try:
        payload = {
            'text': message,
            'username': 'slackbot',
            'icon_emoji': icon_emoji,
            'mrkdwn': True
        }
        requests.post(slack_webhook_url, json=payload)
    except Exception as e:
        logger.error(f"❌ error in send_to_slack: {e}")

def send_to_discord(message):
    try:
        payload = {
            'content': message
        }
        requests.post(discord_webhook_url, json=payload)
    except Exception as e:
        logger.error(f"❌ Error in send_to_discord: {e}")

def send_notification(message, slack_icon_emoji=':chart_with_upwards_trend:'):
    # send to slack if webhook URL is set
    send_to_slack(message, slack_icon_emoji) if len(slack_webhook_url) > 0 else logger.debug("no slack webhook URL found. skipping...")
    # send to discord if webhook URL is set
    send_to_discord(message) if len(discord_webhook_url) > 0 else logger.debug("no discord webhook URL found. skipping...")
    logger.info(message)

def main():
    logger.info('starting oss-activity-monitor...')

    # pull providers
    logger.info('pulling required providers from StackQL registry')
    providers = ['github', 'homebrew']
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
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_stargazers")[0]['count']
    send_notification(f"⭐ found {init_count} initial repo stargazers for {owner}/{repo}")

    # github repo watchers
    logger.info(f"👀 initializing materialized view for repo watchers for {owner}/{repo}...")
    mat_view_query = """
    CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_watchers AS 
    SELECT login FROM github.activity.repo_watchers 
    WHERE owner = '%s' and repo = '%s'
    """ % (owner, repo)
    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_watchers")[0]['count']
    send_notification(f"👀 found {init_count} initial repo watchers for {owner}/{repo}")

    # github repo forks
    logger.info(f"🍴 initializing materialized view for repo forks for {owner}/{repo}...")
    mat_view_query = """
    CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_forks AS 
    SELECT JSON_EXTRACT(owner, '$.login') AS login FROM github.repos.forks 
    WHERE owner = '%s' and repo = '%s'
    """ % (owner, repo)
    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_forks")[0]['count']
    send_notification(f"🍴 found {init_count} initial repo forks for {owner}/{repo}")

    # github repo issues
    logger.info(f"📊 initializing materialized view for repo issues for {owner}/{repo}...")
    mat_view_query = """
    CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_issues AS 
    SELECT id, json_extract(user, '$.login') as reporter
    FROM github.issues.issues
    WHERE owner = '%s' and repo = '%s'
    """ % (owner, repo)
    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_repo_issues")[0]['count']
    send_notification(f"📊 found {init_count} initial repo issues for {owner}/{repo}")

    # github org followers
    logger.info(f"🙋 initializing materialized view for org followers for {owner}...")
    mat_view_query = """
    CREATE OR REPLACE MATERIALIZED VIEW mvw_github_org_followers AS 
    SELECT login FROM github.users.followers WHERE username = '%s'
    """ % (owner)
    run_stackql_stmt(mat_view_query)
    init_count = stackql.execute("SELECT COUNT(*) as count FROM mvw_github_org_followers")[0]['count']
    send_notification(f"🙋 found {init_count} initial org followers for {owner}")

    # github release assset downloads
    logger.info(f"📦 initializing materialized view for release asset downloads for {owner}/{repo}...")
    mat_view_query = """
    CREATE OR REPLACE MATERIALIZED VIEW mvw_github_release_asset_downloads AS 
    SELECT
    SPLIT_PART(JSON_EXTRACT(json_each.value, '$.browser_download_url'), '/', -1) as asset_name,
    SUM(JSON_EXTRACT(json_each.value, '$.download_count')) as download_count
    FROM
    github.repos.releases, json_each(assets)
    WHERE owner = '%s' AND repo = '%s'
    GROUP BY asset_name
    """ % (owner, repo)
    run_stackql_stmt(mat_view_query)
    asset_downloads = stackql.execute("SELECT asset_name, download_count FROM mvw_github_release_asset_downloads")
    for asset in asset_downloads:
        send_notification(f"📦 found {asset['download_count']} initial downloads for {asset['asset_name']}")

    # homebrew downloads
    logger.info(f"🍺 initializing materialized view for homebrew downloads for {formula_name}...")
    mat_view_query = """
    CREATE OR REPLACE MATERIALIZED VIEW mvw_homebrew_downloads AS 
    SELECT
    JSON_EXTRACT(JSON_EXTRACT(analytics, '$.install.30d'), '$.' || formula_name) as installs_30d,
    JSON_EXTRACT(JSON_EXTRACT(analytics, '$.install.90d'), '$.' || formula_name) as installs_90d,
    JSON_EXTRACT(JSON_EXTRACT(analytics, '$.install.365d'), '$.' || formula_name) as installs_365d
    FROM
    homebrew.formula.formula
    WHERE formula_name = '%s'
    """ % (formula_name)
    run_stackql_stmt(mat_view_query)
    init_count_30d = stackql.execute("SELECT installs_30d FROM mvw_homebrew_downloads")[0]['installs_30d']
    send_notification(f"🍺 found {init_count_30d} initial 30d downloads for {formula_name}")
    init_count_90d = stackql.execute("SELECT installs_90d FROM mvw_homebrew_downloads")[0]['installs_90d']
    send_notification(f"🍺 found {init_count_90d} initial 90d downloads for {formula_name}")
    init_count_365d = stackql.execute("SELECT installs_365d FROM mvw_homebrew_downloads")[0]['installs_365d']
    send_notification(f"🍺 found {init_count_365d} initial 365d downloads for {formula_name}")        

if __name__ == '__main__':
    main()