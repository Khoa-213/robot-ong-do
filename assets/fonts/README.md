## Demo Fonts

### Playwrite VN

- File: `PlaywriteVN-wght.ttf`
- Style: handwriting
- License: SIL Open Font License 1.1
- Source: `google/fonts`, `ofl/playwritevn`
- Good for Vietnamese handwriting demos because the family is tagged for `vi_Latn`.

Preview command:

```powershell
python -m src.font_skeleton_pipeline --text-file assets\text_samples\tam_vi.txt --font assets\fonts\PlaywriteVN-wght.ttf --preview-only
```

If your Windows shell displays Vietnamese text incorrectly, prefer `--text-file` over typing the text directly on the command line.
