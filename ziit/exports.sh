export APP_ZIIT_PASTEO_KEY="k4.local.$(derive_entropy "${app_entropy_identifier}-ZIIT_PASTEO_KEY" | head -c32 | base64)"
