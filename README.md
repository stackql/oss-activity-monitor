# Open Source Project Activity Monitor

Get real-time alerts in Slack or Discord for GitHub project activity.  

IMAGE

This project uses [__stackql__](https://github.com/stackql/stackql) to perform real-time open source project activity monitoring, this includes real time notification of:

- ⭐ new GitHub repo stargazers
- 👀 new GitHub repo watchers
- 🍴 new GitHub repo forks
- 📊 new GitHub repo issues
- 🙋 new GitHub org followers
- 📦 new GitHub release asset downloads
- 🍺 new homebrew downloads

## How it works

Materialized views and `SELECT` statements are used to capture and compare state between current and previous metrics for GitHub and Homebrew monitored endpoints, this is described in the diagram here:  

```mermaid
graph TB
    A[CREATE MATERIALIZED VIEW\nof GitHub or Homebrew metric] --> B[SELECT query for\nGitHub or Homebrew metric]
    B --> C[Compare current state\nto previous state]
    C --> D[Send Slack and/or Discord\nmessage with alert]
    D --> B
```
for example, here given this materialized view created and populated using `stackql`:  

```sql
CREATE OR REPLACE MATERIALIZED VIEW mvw_github_repo_stargazers AS 
SELECT login FROM github.activity.repo_stargazers
WHERE owner = 'your-org' and repo = 'your-repo'
```

the following `stackql` query polls GitHub for new stargazers...

```sql
SELECT c.login
FROM github.activity.repo_stargazers c
LEFT JOIN mvw_github_repo_stargazers mvw
ON c.login = mvw.login
WHERE mvw.login IS NULL
AND c.owner = 'your-org' AND c.repo = 'your-repo'
```

then the state is refreshed using...

```sql
REFRESH MATERIALIZED VIEW mvw_github_repo_stargazers
```

similar patterns are repeated for repo watchers, issues, org followers, release asset downloads and homebrew downloads.

## Deployment

basic configuration required (provided using environment variables, a `.env` file in the example below):  

| Variable                   | Description                                                                       | Example Value                                    |
|----------------------------|-----------------------------------------------------------------------------------|--------------------------------------------------|
| `LOG_LEVEL`                | Log level (INFO for general logs; DEBUG for detailed logging)                     | INFO                                             |
| `SLEEP_INTERVAL`           | Time delay in seconds between request loops                                       | 5                                                |
| `GITHUB_REPO`              | GitHub repository name                                                            | stackql                                          |
| `GITHUB_REPO_OWNER`        | GitHub organization or owner name                                                 | stackql                                          |
| `HOMEBREW_FORMULA_NAME`    | Homebrew formula name, if available                                               | stackql                                          |
| `STACKQL_GITHUB_USERNAME`  | Your GitHub username                                                              | jeffreyaven                                      |
| `STACKQL_GITHUB_PASSWORD`  | Your GitHub personal access token                                                 | ghp_yourpersonalaccesstoken                      |
| `SLACK_WEBHOOK_URL`        | Slack webhook URL for sending notifications                                       | https://hooks.slack.com/services/...             |
| `DISCORD_WEBHOOK_URL`      | Discord webhook URL for sending notifications                                     | https://discord.com/api/webhooks/...             |

### Building the container

```bash
docker build --no-cache -t oss-activity-monitor .
```

### Running the container

```bash
docker run --env-file .env oss-activity-monitor
```

### Stopping the container

```bash
docker stop $(docker ps -a -q --filter ancestor=oss-activity-monitor)
```