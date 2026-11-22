#!/bin/sh
# B21: offline kit for the finale (docs/SUBMISSION.md, 19:00): a zip of the repository at the tag, the Docker
# image saved to a file, and SHA256SUMS - everything needed to run `make finale-preflight` on another laptop
# without network. Writes only into dist/ (git-ignored). Usage:  sh scripts/offline_kit.sh [tag]   (= make offline-kit)
set -e
cd "$(dirname "$0")/.."
REF="${1:-v1.1-submission}"
if ! git rev-parse -q --verify "$REF^{commit}" >/dev/null; then
  echo "offline-kit: no tag $REF yet - using HEAD (re-run after tagging)"; REF=HEAD
fi
SHA=$(git rev-parse --short=12 "$REF")
mkdir -p dist
git archive --format=zip --prefix="auditenv-$SHA/" -o "dist/auditenv-$SHA.zip" "$REF"
echo "offline-kit: dist/auditenv-$SHA.zip ($(du -h "dist/auditenv-$SHA.zip" | cut -f1))"
if command -v docker >/dev/null 2>&1 && docker image inspect auditenv >/dev/null 2>&1; then
  docker save auditenv | gzip -1 > "dist/auditenv-image-$SHA.tar.gz"
  echo "offline-kit: dist/auditenv-image-$SHA.tar.gz ($(du -h "dist/auditenv-image-$SHA.tar.gz" | cut -f1))"
else
  echo "offline-kit: no local image 'auditenv' (run make docker-build first) - image skipped"
fi
(cd dist && sha256sum auditenv-*"$SHA"* > "SHA256SUMS-$SHA")
cat "dist/SHA256SUMS-$SHA"
cat <<EOT
On the other laptop (offline):
  sha256sum -c SHA256SUMS-$SHA
  unzip auditenv-$SHA.zip && cd auditenv-$SHA
  gunzip -c ../auditenv-image-$SHA.tar.gz | docker load
  make finale-preflight
EOT
