# A stable per-install session secret. The image would generate and persist one under /config on its own;
# deriving it from the device seed keeps it out of a file and identical across reinstalls of the same data.
export APP_UCHIYOMI_JWT_SECRET="$(derive_entropy "${app_entropy_identifier}-jwt-secret")"
