**step1:**
<br>
python data_processor.py --input-dir ./raw_data/ --user-action-file user_action.csv --user-profile-file user_profile.csv --poi-info-file poi_info.csv --poi-geographic-file poi_info_groupby_geographic.csv

**step2:**
<br>
python post_process_features.py
