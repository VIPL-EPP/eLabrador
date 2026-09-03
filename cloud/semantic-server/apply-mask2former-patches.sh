#!/usr/bin/env bash

set -euo pipefail

readonly MASK2FORMER_REVISION="9b0651c6c1d5b3af2e6da0589b719c514ec0d69a"

usage() {
    cat <<'EOF'
Usage:
  apply-mask2former-patches.sh <h100|bw1000> <Mask2Former source> [--check]

Examples:
  ./apply-mask2former-patches.sh h100 /opt/Mask2Former
  ./apply-mask2former-patches.sh bw1000 /opt/Mask2Former --check

The source repository must be at Mask2Former revision
9b0651c6c1d5b3af2e6da0589b719c514ec0d69a. --check validates the complete
ordered patch set without changing the source tree.
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage >&2
    exit 2
fi

platform=$1
source_argument=$2
check_only=false

if [[ $# -eq 3 ]]; then
    [[ $3 == "--check" ]] || die "unknown option: $3"
    check_only=true
fi

case "$platform" in
    h100|bw1000) ;;
    *) die "platform must be h100 or bw1000" ;;
esac

[[ -d $source_argument ]] || die "source directory does not exist: $source_argument"
command -v git >/dev/null 2>&1 || die "git is required"

script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
patch_root="$script_dir/patches/mask2former"

git -C "$source_argument" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "source directory is not a Git work tree: $source_argument"
source_dir=$(git -C "$source_argument" rev-parse --show-toplevel)
current_revision=$(git -C "$source_dir" rev-parse HEAD)
[[ $current_revision == "$MASK2FORMER_REVISION" ]] || die \
    "Mask2Former revision mismatch: expected $MASK2FORMER_REVISION, got $current_revision"

core_patches=(
    "$patch_root/core/torch210-msdeformattn.patch"
    "$patch_root/core/host-side-spatial-shapes.patch"
    "$patch_root/core/decoder-attn-mask-nosync.patch"
    "$patch_root/core/swin-attention-flex-fused.patch"
    "$patch_root/core/swin-ffn-inductor-experimental.patch"
    "$patch_root/core/decoder-pointwise-inductor-experimental.patch"
    "$patch_root/core/swin-attention-spatial-layout-fused.patch"
    "$patch_root/core/msdeform-forward-h100-fixed-fp32.patch"
    "$patch_root/core/msdeform-encoder-residual-norm-inductor.patch"
    "$patch_root/core/upsample-pointwise-inductor.patch"
)

h100_patches=(
    "$patch_root/h100/swin-ffn-bf16-experimental.patch"
    "$patch_root/h100/semantic-batch-postprocess-experimental.patch"
    "$patch_root/h100/swin-qkv-bf16-experimental.patch"
    "$patch_root/h100/msdeform-encoder-ffn-bf16-experimental.patch"
)

bw1000_patches=(
    "$patch_root/bw1000/mask2former-torch25-dynamo.patch"
    "$patch_root/bw1000/mask2former-msda-rocm.patch"
    "$patch_root/bw1000/bw1000-msdeform-fixed64.patch"
)

patches=("${core_patches[@]}")
if [[ $platform == "h100" ]]; then
    patches+=("${h100_patches[@]}")
else
    patches+=("${bw1000_patches[@]}")
fi

target_files=(
    mask2former/maskformer_model.py
    mask2former/modeling/backbone/swin.py
    mask2former/modeling/pixel_decoder/msdeformattn.py
    mask2former/modeling/pixel_decoder/ops/modules/ms_deform_attn.py
    mask2former/modeling/pixel_decoder/ops/setup.py
    mask2former/modeling/pixel_decoder/ops/src/cuda/ms_deform_attn_cuda.cu
    mask2former/modeling/pixel_decoder/ops/src/cuda/ms_deform_im2col_cuda.cuh
    mask2former/modeling/transformer_decoder/mask2former_transformer_decoder.py
)

for patch_file in "${patches[@]}"; do
    [[ -f $patch_file ]] || die "missing bundled patch: $patch_file"
done

for relative_path in "${target_files[@]}"; do
    [[ -f "$source_dir/$relative_path" ]] || die \
        "Mask2Former source is missing: $relative_path"
done

dirty_targets=$(git -C "$source_dir" status --porcelain --untracked-files=no -- \
    "${target_files[@]}")
[[ -z $dirty_targets ]] || die \
    "patch target files are already modified; use a clean checkout of $MASK2FORMER_REVISION"

temporary_root=$(mktemp -d "${TMPDIR:-/tmp}/elabrador-mask2former-patches.XXXXXX")
staged_source="$temporary_root/source"
mkdir -p "$staged_source"
cleanup() {
    rm -rf -- "$temporary_root"
}
trap cleanup EXIT

# Preflight the complete ordered chain against copies of every target file. This
# catches version/order problems before the real source tree is modified.
for relative_path in "${target_files[@]}"; do
    mkdir -p "$staged_source/$(dirname -- "$relative_path")"
    cp -- "$source_dir/$relative_path" "$staged_source/$relative_path"
done

for patch_file in "${patches[@]}"; do
    patch_name=${patch_file#"$patch_root/"}
    if ! git -C "$staged_source" apply --check -- "$patch_file"; then
        die "patch preflight failed at $patch_name"
    fi
    git -C "$staged_source" apply -- "$patch_file"
done

if [[ $check_only == true ]]; then
    printf 'Patch set is applicable: platform=%s revision=%s patches=%d\n' \
        "$platform" "$MASK2FORMER_REVISION" "${#patches[@]}"
    exit 0
fi

applied=()
for patch_file in "${patches[@]}"; do
    patch_name=${patch_file#"$patch_root/"}
    if git -C "$source_dir" apply -- "$patch_file"; then
        applied+=("$patch_file")
        printf 'Applied %s\n' "$patch_name"
        continue
    fi

    printf 'error: failed to apply %s; rolling back this patch set\n' \
        "$patch_name" >&2
    for ((index=${#applied[@]} - 1; index >= 0; index--)); do
        git -C "$source_dir" apply --reverse -- "${applied[index]}" \
            || printf 'error: rollback failed for %s\n' "${applied[index]}" >&2
    done
    exit 1
done

printf 'Applied Mask2Former patch set: platform=%s revision=%s patches=%d\n' \
    "$platform" "$MASK2FORMER_REVISION" "${#patches[@]}"
printf '%s\n' 'Rebuild MultiScaleDeformableAttention before starting the service.'
