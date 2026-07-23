# 96-Well Plate QC Website

This is a browser-based Streamlit application. End users do not need Python
once the application is hosted.

## Deploy on Streamlit Community Cloud

1. Create a new GitHub repository.
2. Upload all files from this folder, including the `.streamlit` folder.
3. Sign in to Streamlit Community Cloud.
4. Create a new app and select the repository.
5. Set the main file path to `app.py`.
6. Deploy.

The hosting service will provide a public web address that can be opened from
Windows, macOS, tablets, or other devices.

## Run locally for testing

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Website features

- Upload a 96-well plate CSV
- Enter sample name and report title
- Use the automatic or a custom plate Z-score threshold
- Preview the generated QC report
- Download the HTML report
- Download group statistics
- Download candidate-hit wells

## Z-score logic

Each well uses the whole-plate Z-score:

`(well value - plate mean) / plate standard deviation`

The default hit threshold is the highest whole-plate Z-score among controls
E12, F12, G12, and H12.
