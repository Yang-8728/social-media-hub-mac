ACCOUNT_FOLDER_MAPPING = {
    "ai_vanvan": "gaoxiao",
    "aigf8728": "gf"
}

FOLDER_ACCOUNT_MAPPING = {v: k for k, v in ACCOUNT_FOLDER_MAPPING.items()}


def get_folder_name(instagram_account: str) -> str:
    return ACCOUNT_FOLDER_MAPPING.get(instagram_account, instagram_account)

def get_account_name(folder_name: str) -> str:
    return FOLDER_ACCOUNT_MAPPING.get(folder_name, folder_name)

def get_display_name(instagram_account: str) -> str:
    return get_folder_name(instagram_account)
