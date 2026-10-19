"""SPEED bench for the Reader V3 README (written 2026-10-14 06:42:17, before any timing). Fair rules:
- same input: the never-seen 1447 w058 suite stack (24 layers, 1564 x 3826 px = 6.0 Mpx), ONE layer order, same GPU (RTX 5070 Ti),
  nothing else on the GPU; model load + CUDA warm-up EXCLUDED (one untimed warm-up pass on the same input, then 1 timed pass).
- each model at its recommended settings: Reader V3 = team CLI path (fl_reader: overlap 0.5, hann, batch 8, no-compile);
  Reader v2 = same path; v8-in = predict_stack stride 21 (its native, published-quality stride), batch 8;
  Hecate = its own hecate.py, bf16, batch 8, on the 9.6 um resample (resampling time INCLUDED: it is part of using Hecate).
- report seconds and Mpx/s per model -> results/speed.json. The README claims only that Reader V3 was the fastest.
Record of how the timing was run: it uses the author's local evaluation helpers (fl_reader, v8ft_eval), which are not part
of this repository, so it documents the method rather than running standalone."""
import json, os, subprocess, sys, tempfile, time
import numpy as np, cv2, zarr, torch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.join(ROOT, 'vendor'))
import fl_reader  # noqa: E402
import v8ft_eval as E  # noqa: E402

OUT = os.path.join(ROOT, 'data', 'speedbench'); os.makedirs(OUT, exist_ok=True)
SV = os.path.join(E.EV, 'v2', 'w058_sv.zarr')                                   # the suite zarr of the stack (24, H, W)
st = np.load(os.path.join(E.SU, 'w058_stack.npy')); H, W = st.shape[:2]; MPX = H * W / 1e6
R = {'input': f'1447 w058 suite region {W}x{H} = {MPX:.2f} Mpx, 24 layers, one layer order', 'gpu': torch.cuda.get_device_name(0)}


def sync():
    torch.cuda.synchronize()


def bench_koine(name, ck):
    rd = fl_reader.Reader(ck, SV, workers=2); tmp = tempfile.mkdtemp()
    import koine_machines.inference.infer as I
    from pathlib import Path
    def once(tag):
        o = Path(tmp) / f'{tag}.tif'
        I.infer_single_zarr(args=rd.args, configured_model=rd.cm, device=rd.dev, input_zarr=str(SV), output_tiff=o, layer_direction='forward')
    once('warm'); sync(); t = time.perf_counter(); once('timed'); sync(); dt = time.perf_counter() - t
    R[name] = {'seconds': round(dt, 2), 'mpx_per_s': round(MPX / dt, 3)}; print(name, R[name], flush=True); del rd; torch.cuda.empty_cache()


def bench_v8in():
    sys.path.insert(0, E.MD); from ink8um.inference import predict_stack
    m = E.load_model('base'); a = np.ascontiguousarray(np.clip(st, 0, 200).astype(np.uint8))
    predict_stack(m, a[:512, :512], reverse=True, stride=21, batch_size=8, num_workers=0); sync()
    t = time.perf_counter(); predict_stack(m, a, reverse=True, stride=21, batch_size=8, num_workers=0); sync(); dt = time.perf_counter() - t
    R['v8-in (stride 21)'] = {'seconds': round(dt, 2), 'mpx_per_s': round(MPX / dt, 3)}; print('v8-in', R['v8-in (stride 21)'], flush=True)
    del m; torch.cuda.empty_cache()


def bench_hecate():
    Hd = os.path.join(ROOT, 'models', 'hecate'); py = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe'); tmp = tempfile.mkdtemp()
    def once(tag):
        t0 = time.perf_counter()
        a = st[..., ::-1].transpose(2, 0, 1); fz = 8.64 / 9.6; nz, ny, nx = a.shape; oy, ox, oz = int(round(ny * fz)), int(round(nx * fz)), int(round(nz * fz))
        xy = np.stack([cv2.resize(np.ascontiguousarray(a[k]), (ox, oy), interpolation=cv2.INTER_AREA) for k in range(nz)])
        zs = (np.arange(oz) + 0.5) / fz - 0.5; z0 = np.clip(np.floor(zs).astype(int), 0, nz - 1); z1 = np.clip(z0 + 1, 0, nz - 1); w = np.clip(zs - z0, 0, 1)
        out = np.stack([np.round((1 - w[k]) * xy[z0[k]] + w[k] * xy[z1[k]]).astype(np.uint8) for k in range(oz)])
        npy = os.path.join(tmp, f'{tag}.npy'); np.save(npy, out)
        subprocess.check_call([py, os.path.join(Hd, 'hecate.py'), '--checkpoint', os.path.join(Hd, 'hecate_9.6um.pth'), '--input', npy,
                               '--spacing-um', '9.6', '--output', os.path.join(tmp, f'{tag}.png'), '--device', 'cuda', '--precision', 'bf16',
                               '--batch-size', '8'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)
        return time.perf_counter() - t0
    once('warm'); dt = once('timed')
    R['hecate'] = {'seconds': round(dt, 2), 'mpx_per_s': round(MPX / dt, 3),
                   'note': 'includes model load (separate process) + 9.6 um resample'}; print('hecate', R['hecate'], flush=True)


if __name__ == '__main__':
    bench_koine('reader-v3', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'checkpoints', 'reader-v3.pth'))
    bench_koine('reader-v2', os.path.join(ROOT, 'data', 'v2', 'train', 'ckpt_040000.pth'))
    bench_v8in()
    bench_hecate()
    json.dump(R, open(os.path.join(OUT, 'speed.json'), 'w'), indent=1); print('SPEED_DONE', flush=True)
