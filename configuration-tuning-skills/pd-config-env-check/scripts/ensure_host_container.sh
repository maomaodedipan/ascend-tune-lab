#!/usr/bin/env bash
# Ensure one vLLM-Ascend container per host (Path C).
# A2/A3 docker run templates follow:
#   https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/GLM5.html
# Image selection when --image omitted: try higher tags first, fall back to lower
#   (local image → docker pull → next candidate). Host may only run docker*.
# Multi-host: caller MUST resolve once and pass the same --image to every host
#   (do not let each host fall back independently).
#
# Usage (run ON the target host):
#   ensure_host_container.sh --name NAME --device-type A2|A3 [--image IMAGE]
set -euo pipefail

NAME=""
IMAGE=""
DEVICE_TYPE="${DEVICE_TYPE:-A2}"
REPO="quay.io/ascend/vllm-ascend"

# High → low preference (Ubuntu tags). Keep newest first when bumping.
# A2 (no -a3 suffix) / A3 (*-a3).
CANDIDATES_A2=(
  "${REPO}:v0.23.0rc1"
  "${REPO}:v0.22.1rc1"
)
CANDIDATES_A3=(
  "${REPO}:v0.23.0rc1-a3"
  "${REPO}:v0.22.1rc1-a3"
)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --device-type) DEVICE_TYPE="$2"; shift 2 ;;
    --npu-count) shift 2 ;; # ignored; device list comes from A2/A3 template
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

if [[ -z "$NAME" ]]; then
  echo "ERROR: --name required"; exit 2
fi

DT=$(echo "$DEVICE_TYPE" | tr '[:lower:]' '[:upper:]')
case "$DT" in
  A2|A3) ;;
  *) echo "ERROR: --device-type must be A2 or A3 (got $DEVICE_TYPE)"; exit 2 ;;
esac

# True when caller pinned --image (required for multi-host uniformity).
IMAGE_PINNED=0
if [[ -n "$IMAGE" ]]; then
  IMAGE_PINNED=1
fi

# Return 0 if image usable locally or after pull. Logs go to stderr.
try_image() {
  local img="$1"
  if docker image inspect "$img" >/dev/null 2>&1; then
    echo "IMAGE_LOCAL ok=$img" >&2
    return 0
  fi
  echo "IMAGE_PULL trying=$img" >&2
  if docker pull "$img" >/dev/null; then
    echo "IMAGE_PULL ok=$img" >&2
    return 0
  fi
  echo "IMAGE_PULL fail=$img" >&2
  return 1
}

# Prints only the selected image ref on stdout.
resolve_image() {
  if [[ -n "$IMAGE" ]]; then
    if try_image "$IMAGE"; then
      printf '%s\n' "$IMAGE"
      return 0
    fi
    echo "ERROR: specified --image unavailable: $IMAGE" >&2
    return 1
  fi

  local -a cands=()
  if [[ "$DT" == "A3" ]]; then
    cands=("${CANDIDATES_A3[@]}")
  else
    cands=("${CANDIDATES_A2[@]}")
  fi

  local img
  for img in "${cands[@]}"; do
    if try_image "$img"; then
      printf '%s\n' "$img"
      return 0
    fi
  done
  echo "ERROR: no usable image for device_type=$DT; tried: ${cands[*]}" >&2
  return 1
}

RESOLVED="$(resolve_image)"
IMAGE="$RESOLVED"
echo "IMAGE_SELECTED=$IMAGE device_type=$DT"

if docker inspect -f '{{.State.Status}}' "$NAME" >/dev/null 2>&1; then
  ST=$(docker inspect -f '{{.State.Status}}' "$NAME")
  CUR_IMG=$(docker inspect -f '{{.Config.Image}}' "$NAME")
  # Multi-host path passes --image; refuse silent mismatch against required tag.
  if [[ "$IMAGE_PINNED" -eq 1 && "$CUR_IMG" != "$RESOLVED" ]]; then
    echo "ERROR: container=$NAME image=$CUR_IMG != required=$RESOLVED (cluster must use the same image)" >&2
    exit 3
  fi
  if [[ "$ST" == "running" ]]; then
    echo "EXISTS_RUNNING name=$NAME image=$CUR_IMG device_type=$DT"
    exit 0
  fi
  echo "EXISTS_NOT_RUNNING status=$ST → docker start"
  docker start "$NAME"
  echo "STARTED name=$NAME"
  exit 0
fi

# Shared Ascend control devices + driver mounts (official GLM5 docker tabs).
# --privileged + label=disable: CANN realpath() on OPP proto otherwise EPERM
# in unprivileged containers (SpaceRegistry nullptr / ZerosLike 361001).
COMMON_DEVICES=(
  --device /dev/davinci_manager
  --device /dev/devmm_svm
  --device /dev/hisi_hdc
)
COMMON_MOUNTS=(
  -v /usr/local/dcmi:/usr/local/dcmi
  -v /usr/local/Ascend/driver/tools/hccn_tool:/usr/local/Ascend/driver/tools/hccn_tool
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi
  -v /usr/local/Ascend/driver/lib64/:/usr/local/Ascend/driver/lib64/
  -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info
  -v /etc/ascend_install.info:/etc/ascend_install.info
  -v /root/.cache:/root/.cache
)

echo "CREATING name=$NAME image=$IMAGE device_type=$DT"

if [[ "$DT" == "A3" ]]; then
  # Official A3 tab: davinci0..15, shm-size=1g, net=host
  docker run -d \
    --name "$NAME" \
    --privileged \
    --security-opt label=disable \
    --net=host \
    --shm-size=1g \
    --device /dev/davinci0 \
    --device /dev/davinci1 \
    --device /dev/davinci2 \
    --device /dev/davinci3 \
    --device /dev/davinci4 \
    --device /dev/davinci5 \
    --device /dev/davinci6 \
    --device /dev/davinci7 \
    --device /dev/davinci8 \
    --device /dev/davinci9 \
    --device /dev/davinci10 \
    --device /dev/davinci11 \
    --device /dev/davinci12 \
    --device /dev/davinci13 \
    --device /dev/davinci14 \
    --device /dev/davinci15 \
    "${COMMON_DEVICES[@]}" \
    "${COMMON_MOUNTS[@]}" \
    "$IMAGE" \
    sleep infinity
else
  # Official A2 tab: davinci0..7, shm-size=1g, net=host
  docker run -d \
    --name "$NAME" \
    --privileged \
    --security-opt label=disable \
    --shm-size=1g \
    --net=host \
    --device /dev/davinci0 \
    --device /dev/davinci1 \
    --device /dev/davinci2 \
    --device /dev/davinci3 \
    --device /dev/davinci4 \
    --device /dev/davinci5 \
    --device /dev/davinci6 \
    --device /dev/davinci7 \
    "${COMMON_DEVICES[@]}" \
    "${COMMON_MOUNTS[@]}" \
    "$IMAGE" \
    sleep infinity
fi

echo "CREATED name=$NAME"
docker inspect -f 'status={{.State.Status}} image={{.Config.Image}}' "$NAME"
