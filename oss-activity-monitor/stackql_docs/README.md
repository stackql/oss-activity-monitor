# oss-activity-monitor


```
export AZURE_SUBSCRIPTION_ID=631d1c6d-2a65-43e7-93c2-688bfe4e1468

stackql-deploy build oss-activity-monitor prd -e AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID --dry-run

stackql-deploy \
--custom-registry="https://registry-dev.stackql.app/providers" \
--download-dir . \
build oss-activity-monitor prd \
-e AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID --log-level DEBUG

stackql-deploy \
--custom-registry="https://registry-dev.stackql.app/providers" \
--download-dir . \
test oss-activity-monitor prd \
-e AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID

stackql-deploy \
--custom-registry="https://registry-dev.stackql.app/providers" \
--download-dir . \
teardown oss-activity-monitor prd \
-e AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID
```
