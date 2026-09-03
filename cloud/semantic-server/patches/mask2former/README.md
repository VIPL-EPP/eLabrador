# Mask2Former Patch Sets

These patches target upstream Mask2Former revision
`9b0651c6c1d5b3af2e6da0589b719c514ec0d69a`. Apply the complete ordered set
with [`apply-mask2former-patches.sh`](../../apply-mask2former-patches.sh):

```bash
./apply-mask2former-patches.sh h100 /path/to/Mask2Former
./apply-mask2former-patches.sh bw1000 /path/to/Mask2Former
```

`core/` contains the shared, ordered source changes through the fixed-shape
fusion path. `h100/` adds the validated P13/P14 opt-in candidates. `bw1000/`
adds PyTorch 2.5/ROCm compatibility and the measured 64-thread MS-Deform
variant. Files for rejected, superseded, or parameter-sweep experiments are not
distributed here.

Some retained filenames contain `experimental` because they originated as
measured candidates. Their optimized modes remain opt-in until labelled-set
mIoU validation is complete; the patches preserve the `legacy` fallback.

The patches contain modifications to Mask2Former. Upstream copyright and
license terms are preserved in [`LICENSE.Mask2Former`](LICENSE.Mask2Former).
