from __future__ import annotations
import sys, torch
def main()->int:
    print("="*70); print("INTEL XPU CHECK"); print("="*70)
    print("Python:",sys.version.split()[0]); print("PyTorch:",torch.__version__)
    ok=hasattr(torch,"xpu") and torch.xpu.is_available()
    print("XPU available:",ok)
    if not ok: return 2
    print("Device:",torch.xpu.get_device_name(0))
    print("BF16:",torch.xpu.is_bf16_supported())
    x=torch.randn(256,256,device="xpu"); y=x@x; torch.xpu.synchronize()
    print("Tensor:",y.device,tuple(y.shape),"OK")
    return 0
if __name__=="__main__": raise SystemExit(main())
