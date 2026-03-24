"""
账号名映射工具
处理Instagram账号名与本地文件夹名的映射关系
"""

# Instagram账号名 -> 本地文件夹名映射
ACCOUNT_FOLDER_MAPPING = {
    "ai_vanvan": "gaoxiao",    # 搞笑内容账户
    "aigf8728": "gf"           # 女朋友账户
}

# 本地文件夹名 -> Instagram账号名映射（反向）
FOLDER_ACCOUNT_MAPPING = {
    "gaoxiao": "ai_vanvan",
    "gf": "aigf8728"
}

def get_folder_name(instagram_account: str) -> str:
    """
    根据Instagram账号名获取本地文件夹名
    
    Args:
        instagram_account: Instagram账号名，如 "ai_vanvan"
        
    Returns:
        本地文件夹名，如 "gaoxiao"
    """
    return ACCOUNT_FOLDER_MAPPING.get(instagram_account, instagram_account)

def get_account_name(folder_name: str) -> str:
    """
    根据本地文件夹名获取Instagram账号名
    
    Args:
        folder_name: 本地文件夹名，如 "gaoxiao"
        
    Returns:
        Instagram账号名，如 "ai_vanvan"
    """
    return FOLDER_ACCOUNT_MAPPING.get(folder_name, folder_name)

def get_display_name(instagram_account: str) -> str:
    """
    获取用户友好的显示名称
    
    Args:
        instagram_account: Instagram账号名
        
    Returns:
        用户友好的显示名称
    """
    return get_folder_name(instagram_account)

def get_all_accounts():
    """
    获取所有配置的账户信息
    
    Returns:
        包含账户映射信息的字典
    """
    return {
        instagram_account: {
            "instagram_username": instagram_account,
            "folder_name": folder_name,
            "display_name": folder_name
        }
        for instagram_account, folder_name in ACCOUNT_FOLDER_MAPPING.items()
    }
