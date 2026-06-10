# Pipeline tao mini motion dataset cho robot arm

## 1. Muc tieu

Pipeline nay tao mot mini motion dataset cho canh tay robot de replay hoac training nhe trong Unity va NVIDIA Isaac Sim. Dinh dang chuan noi bo la:

```text
state/action = [x, y, z, roll, pitch, yaw, gripper]
```

Mac dinh pipeline luon sinh du lieu synthetic de demo duoc ngay, ke ca khi chua tai duoc Open X-Embodiment.

## 2. Vi sao khong clone toan bo dataset tu GitHub

Repo `google-deepmind/open_x_embodiment` chu yeu chua code, config, metadata, Colab va script. Dataset that rat lon, duoc phan phoi theo RLDS/TFDS va Google Cloud Storage, nen khong nen hieu la co the `git clone` dataset day du tu GitHub.

Script `scripts/clone_openx_repo.py` chi clone source code vao:

```text
external/open_x_embodiment
```

Neu folder da ton tai, script se bo qua an toan. Them `--pull` neu muon cap nhat bang `git pull --ff-only`.

## 3. Cai dependencies

Phan synthetic/export chi can cac package dang co trong `requirements.txt`: `numpy`, `pandas`, `matplotlib`.

```powershell
pip install -r requirements.txt
```

Doc Open X qua TFDS la optional:

```powershell
pip install -r requirements-openx.txt
```

Tren Windows, TensorFlow co the nang hoac kho cai. Neu gap loi, van co the chay synthetic-only.

## 4. Clone Open X-Embodiment

```powershell
python scripts\clone_openx_repo.py
```

Cap nhat neu repo da co:

```powershell
python scripts\clone_openx_repo.py --pull
```

Script khong xoa du lieu cu.

## 5. Tai/sample dataset Open X

Khong tai toan bo dataset. Chon mot dataset nho hoac dataset da co trong TFDS cache:

```powershell
python scripts\download_openx_sample.py --dataset_name bridge --max_episodes 100
python scripts\inspect_openx_dataset.py --dataset_name bridge
python scripts\filter_openx_trajectories.py --dataset_name bridge --max_episodes 100
```

Mac dinh cac script tren chi doc dataset da co trong TFDS cache. Chuyen `--max_episodes` chi gioi han so episode sau khi dataset da prepare xong; no khong gioi han duoc buoc TFDS download/prepare. Neu muon cho TFDS tu prepare dataset lon, them flag:

```powershell
python scripts\inspect_openx_dataset.py --dataset_name bridge --allow_download_prepare
```

Can than: voi Open X, buoc prepare co the rat lau va rat lon.

Neu du lieu nam san trong TFDS cache, truyen:

```powershell
python scripts\download_openx_sample.py --dataset_name bridge --data_dir C:\Users\<you>\tensorflow_datasets
```

Neu can copy tu Google Cloud Storage, mau lenh co dang:

```powershell
gsutil -m cp -r gs://gdm-robotics-open-x-embodiment/<dataset_name> ~/tensorflow_datasets/
```

Neu TensorFlow/TFDS hoac dataset bi thieu, script se in huong dan thay vi crash kho doc.

## 6. Sinh synthetic dataset

Lenh demo mot buoc:

```powershell
python scripts\build_dataset_pipeline.py --synthetic_only
```

Hoac sinh rieng:

```powershell
python scripts\generate_synthetic_motion_dataset.py --episodes_per_task 20
```

Task synthetic gom: move left/right, move up/down, move forward/backward, draw line, draw square, draw circle, pen lift, pen down. Moi episode co 50 den 200 frame va noise nho.

## 7. Export Unity

```powershell
python scripts\export_to_unity.py --input data\processed\robot_motion_dataset\final_dataset.jsonl --output data\exports\unity\unity_motion_dataset.json
python scripts\replay_unity_export.py
```

Format export:

```json
{
  "metadata": {"format": "robot_motion_unity_v1", "unit": "meters", "fps": 20},
  "episodes": []
}
```

Unity thuong dung Y-up. Mapping mac dinh nam trong `src/dataset/coordinate_converter.py` va co the thay bang config/code rieng khi calibration robot khac.

## 8. Export Isaac Sim

```powershell
python scripts\export_to_isaac.py --input data\processed\robot_motion_dataset\final_dataset.jsonl --output data\exports\isaac\isaac_motion_dataset.json
python scripts\replay_isaac_export.py
```

Exporter cung ghi them:

```text
data/exports/isaac/isaac_motion_dataset.npz
```

Isaac/USD thuong dung Z-up, nen mapping mac dinh giu frame robot X-forward, Y-left/right, Z-up.

Replay truc tiep trong Isaac Sim can chay bang Python cua Isaac, khong phai `.venv` cua project:

```powershell
& "C:\Path\To\IsaacSim\python.bat" scripts\isaac_replay_motion_dataset.py --input data\exports\isaac\isaac_motion_dataset.json --episode_id synthetic_move_left_to_right_0001
```

Script nay tao mot sphere target va cho no chay theo waypoint trong `isaac_motion_dataset.json`. Day la buoc test ket noi dataset -> Isaac truoc khi gan IK/robot USD that.

## 9. Kiem tra trajectory bang hinh 3D

```powershell
python scripts\visualize_trajectory.py --input data\processed\robot_motion_dataset\final_dataset.jsonl --max_episodes 3
```

Anh preview se nam o:

```text
data/processed/trajectory_preview/
```

## 10. Output chinh

Sau khi chay synthetic-only, cac file quan trong la:

```text
data/processed/robot_motion_dataset/final_dataset.jsonl
data/processed/robot_motion_dataset/final_dataset.csv
data/processed/robot_motion_dataset/final_dataset.npz
data/exports/unity/unity_motion_dataset.json
data/exports/isaac/isaac_motion_dataset.json
data/exports/isaac/isaac_motion_dataset.npz
```

## 11. Troubleshooting

- Thieu TensorFlow/TFDS: chay `python scripts\build_dataset_pipeline.py --synthetic_only`.
- Loi `No module named 'importlib_resources'`: chay `pip install -r requirements-openx.txt` trong dung virtualenv, vi mot so TFDS/Open X builder van import goi nay.
- Loi `No module named 'apache_beam'`: dataset builder dang can Beam de prepare data; chay `pip install -r requirements-openx.txt`.
- Dataset Open X khong tim thay: kiem tra `--dataset_name`, `--data_dir`, hoac tai ve TFDS cache truoc.
- Lenh inspect/filter bi dung lau o `Downloading and preparing dataset`: dung lai va chay khong co `--allow_download_prepare`; hay tai mot sample/cache nho truoc.
- `gsutil` khong co: cai Google Cloud SDK va dang nhap dung project/quyen truy cap.
- Unity/Isaac bi sai truc toa do: sua mapping trong `src/dataset/coordinate_converter.py` hoac them mapping rieng theo calibration robot.
- Preview matplotlib loi tren server/headless: script da dung backend `Agg`, nen thu cai lai `matplotlib`.
