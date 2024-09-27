import pandas as pd
import ast

df = pd.read_csv("commits_report.csv", on_bad_lines="skip")

df["Issues"] = df["Issues"].apply(ast.literal_eval)
dict_ = {}


df_final = pd.DataFrame()
dict_ = {}
for index, row in df.iterrows():
    if row["Issues"]["total"] == 0:
        continue
    for issue in row["Issues"]["issues"]:
        if issue["key"] in dict_:
            if (
                issue["issueStatus"] == "FIXED"
                and dict_[issue["key"]]["closed_date"] == ""
            ):
                dict_[issue["key"]]["closed_date"] = row["Date"]
                dict_[issue["key"]]["closed_hash"] = row["Commit Hash"]
                dict_[issue["key"]]["fix_duration"] = (
                    pd.to_datetime(row["Date"])
                    - pd.to_datetime(dict_[issue["key"]]["open_date"])
                ).days
            elif issue["issueStatus"] == "OPEN":
                dict_[issue["key"]]["latest_open"] = row["Date"]
                dict_[issue["key"]]["latest_open_hash"] = row["Commit Hash"]
        else:

            # presume q a primeira aparicao a issue estara aberta
            dict_[issue["key"]] = {
                "sample": row["Sample"],
                "open_date": row["Date"],
                "open_hash": row["Commit Hash"],
                "closed_date": "",
                "closed_hash": "",
                "latest_open": "",
                "latest_open_hash": "",
                "next_commit_date": "",
                "next_commit_hash": "",
                "fix_duration": "",
                "severity": issue["severity"],
                "rule": issue["rule"],
                "flows": issue["flows"],
                "message": issue["message"],
                "effort": issue["effort"],
                "debt": issue["debt"],
                "author": issue["author"],
                "tags": issue["tags"],
                "transitions": issue["transitions"],
                "actions": issue["actions"],
                "comments": issue["comments"],
                "impacts": issue["impacts"],
                "type": issue["type"],
                "quick_fix_available": issue["quickFixAvailable"],
                "clean_code_attribute": issue["cleanCodeAttribute"],
                "clean_code_attributeCategory": issue["cleanCodeAttributeCategory"],
            }

            if "textRange" in issue:
                text_line_start = issue["textRange"].get("startLine", None)
                text_line_end = issue["textRange"].get("endLine", None)
                text_start_offset = issue["textRange"].get("startOffset", None)
                text_end_offset = issue["textRange"].get("endOffset", None)
            else:
                text_line_start = text_line_end = text_start_offset = (
                    text_end_offset
                ) = None

    if len(dict_):
        df_final = (
            pd.DataFrame.from_dict(dict_)
            .T.reset_index()
            .rename(columns={"index": "key"})
        )

commit_hashes = df["Commit Hash"].tolist()
samples = df["Sample"].tolist()

df_final["next_commit_hash"] = df_final.apply(
    lambda x: (
        ""
        if not x["latest_open_hash"]
        else (
            commit_hashes[commit_hashes.index(x["latest_open_hash"]) + 1]
            if (
                commit_hashes.index(x["latest_open_hash"]) + 1 < len(commit_hashes)
                and samples[commit_hashes.index(x["latest_open_hash"]) + 1]
                == x["sample"]
            )
            else ""
        )
    ),
    axis=1,
)

df_final["next_commit_date"] = df_final.apply(
    lambda x: (
        df.loc[df["Commit Hash"] == x["next_commit_hash"], "Date"].values[0]
        if x["next_commit_hash"] != ""
        else ""
    ),
    axis=1,
)


def get_next_commit_info(row, df):
    if row["latest_open_hash"] == "":
        return "", "", ""

    try:
        current_index = df[
            (df["Commit Hash"] == row["latest_open_hash"])
            & (df["Sample"] == row["sample"])
        ].index[0]
    except IndexError:
        return "", "", ""

    if current_index + 1 < len(df):
        next_commit_hash = df.iloc[current_index + 1]["Commit Hash"]
        next_commit_date = df.iloc[current_index + 1]["Date"]
        fix_duration = (
            pd.to_datetime(next_commit_date) - pd.to_datetime(row["open_date"])
        ).days
        if fix_duration < 0:
            return "", "", ""
        return next_commit_hash, next_commit_date, fix_duration

    return "", "", ""


df_final["next_commit_hash"], df_final["next_commit_date"], df_final["fix_duration"] = (
    zip(*df_final.apply(lambda row: get_next_commit_info(row, df), axis=1))
)

print(df_final)
df_final.to_csv("commits_report_analysis.csv", index=False)
