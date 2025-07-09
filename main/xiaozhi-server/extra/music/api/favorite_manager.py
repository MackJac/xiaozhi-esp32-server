import yaml
import os
from typing import List, Dict, Optional
from pathlib import Path
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class FavoriteManager:
    """音乐收藏管理器"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.favorites_file = self.data_dir / "music_favorites.yaml"
        self.favorites = self._load_favorites()
    
    def _load_favorites(self) -> Dict:
        """加载收藏数据"""
        if not self.favorites_file.exists():
            return {}
        
        try:
            with open(self.favorites_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data if data else {}
        except Exception as e:
            logger.bind(tag=TAG).error(f"加载收藏数据失败: {e}")
            return {}
    
    def _save_favorites(self):
        """保存收藏数据"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.favorites, f, allow_unicode=True, default_flow_style=False)
            logger.bind(tag=TAG).info("收藏数据保存成功")
        except Exception as e:
            logger.bind(tag=TAG).error(f"保存收藏数据失败: {e}")
    
    def add_favorite(self, device_id: str, music_info: Dict) -> bool:
        """
        添加收藏
        
        Args:
            device_id: 设备ID
            music_info: 音乐信息
            
        Returns:
            是否成功
        """
        try:
            if device_id not in self.favorites:
                self.favorites[device_id] = []
            
            # 检查是否已收藏
            for favorite in self.favorites[device_id]:
                if favorite.get("id") == music_info.get("id"):
                    logger.bind(tag=TAG).info(f"音乐已收藏: {music_info.get('name')}")
                    return True
            
            # 添加收藏
            self.favorites[device_id].append(music_info)
            self._save_favorites()
            
            logger.bind(tag=TAG).info(f"添加收藏成功: {music_info.get('name')}")
            return True
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"添加收藏失败: {e}")
            return False
    
    def remove_favorite(self, device_id: str, music_id: str) -> bool:
        """
        移除收藏
        
        Args:
            device_id: 设备ID
            music_id: 音乐ID
            
        Returns:
            是否成功
        """
        try:
            if device_id not in self.favorites:
                return False
            
            # 查找并移除
            for i, favorite in enumerate(self.favorites[device_id]):
                if favorite.get("id") == music_id:
                    removed_music = self.favorites[device_id].pop(i)
                    self._save_favorites()
                    logger.bind(tag=TAG).info(f"移除收藏成功: {removed_music.get('name')}")
                    return True
            
            logger.bind(tag=TAG).info(f"未找到收藏的音乐: {music_id}")
            return False
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"移除收藏失败: {e}")
            return False
    
    def get_favorites(self, device_id: str) -> List[Dict]:
        """
        获取收藏列表
        
        Args:
            device_id: 设备ID
            
        Returns:
            收藏列表
        """
        return self.favorites.get(device_id, [])
    
    def is_favorited(self, device_id: str, music_id: str) -> bool:
        """
        检查是否已收藏
        
        Args:
            device_id: 设备ID
            music_id: 音乐ID
            
        Returns:
            是否已收藏
        """
        favorites = self.get_favorites(device_id)
        return any(favorite.get("id") == music_id for favorite in favorites)
    
    def search_favorites(self, device_id: str, keywords: str) -> List[Dict]:
        """
        在收藏中搜索
        
        Args:
            device_id: 设备ID
            keywords: 搜索关键词
            
        Returns:
            匹配的收藏列表
        """
        favorites = self.get_favorites(device_id)
        keywords_lower = keywords.lower()
        
        results = []
        for favorite in favorites:
            name = favorite.get("name", "").lower()
            if keywords_lower in name:
                results.append(favorite)
        
        return results
    
    def clear_favorites(self, device_id: str) -> bool:
        """
        清空收藏
        
        Args:
            device_id: 设备ID
            
        Returns:
            是否成功
        """
        try:
            if device_id in self.favorites:
                self.favorites[device_id] = []
                self._save_favorites()
                logger.bind(tag=TAG).info(f"清空收藏成功: {device_id}")
                return True
            return False
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"清空收藏失败: {e}")
            return False
    
    def get_favorite_count(self, device_id: str) -> int:
        """
        获取收藏数量
        
        Args:
            device_id: 设备ID
            
        Returns:
            收藏数量
        """
        return len(self.get_favorites(device_id)) 