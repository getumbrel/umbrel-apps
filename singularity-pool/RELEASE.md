# SINGULARITY Pool v1.6.0 — Release Package

## Verify before upload

```bash
cd singularity-pool-github-ready
chmod +x scripts/*.sh blackhole-axe-store-singularity-pool/hooks/*
./scripts/verify-version.sh
```

## Create tarball (from app-data folder)

```bash
./scripts/make-release.sh
# creates ../singularity-pool-v1.6.0-FINAL.tar.gz
```

## Upload to GitHub

```bash
cd ~/umbrel/app-data
tar -xzf singularity-pool-v1.6.0-FINAL.tar.gz
cd singularity-pool-github-ready

# IMPORTANT: upload contents of THIS folder to repo root (not the .tar.gz file)
git add -A
git commit -m "v1.6.0: complete release"
git push
```

## Push Docker image

```bash
export GITHUB_TOKEN=ghp_XXXXX
./scripts/push-ghcr.sh 1.6.0
```

## Version must match in

- `VERSION`
- `app/src/config.js`
- `app/package.json`
- `blackhole-axe-store-singularity-pool/umbrel-app.yml`
- `blackhole-axe-store-singularity-pool/docker-compose.yml`
- `umbrel-app-store.yml`
- `.github/workflows/build-and-push.yml`
