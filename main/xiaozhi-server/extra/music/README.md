# 在线音乐功能

本项目实现了完整的在线音乐播放功能，包括音乐搜索、下载、播放、收藏等功能。

## 功能特性

- 🎵 **在线音乐搜索**: 通过关键词搜索在线音乐
- 📥 **智能下载**: 支持边下载边播放，提升用户体验
- 💾 **本地缓存**: 自动缓存已播放的音乐，避免重复下载
- ❤️ **收藏管理**: 支持收藏喜欢的音乐，按设备ID管理
- 🔄 **播放控制**: 支持下一首、停止等播放控制
- ⚡ **预加载**: 智能预加载下一首音乐，减少等待时间

## 目录结构

```
extra/music/
├── api/
│   ├── __init__.py
│   ├── music_api.py          # 音乐API接口封装
│   ├── music_downloader.py   # 音乐下载器
│   ├── favorite_manager.py   # 收藏管理器
│   └── example.py            # 使用示例
└── README.md                 # 本文档
```

## 核心组件

### 1. MusicAPI (music_api.py)

音乐API接口封装，负责与音乐服务进行通信。

```python
from extra.music.api import MusicAPI

api = MusicAPI()
music_list = api.search_music("周杰伦", "device_001")
```

**主要方法:**
- `search_music(keywords, device_id)`: 搜索音乐
- `get_music_info(music_data)`: 解析音乐信息

### 2. MusicDownloader (music_downloader.py)

音乐下载器，支持传统下载和流式下载。

```python
from extra.music.api import MusicDownloader

downloader = MusicDownloader()
cache_path = await downloader.download_music(url, music_id)
```

**主要方法:**
- `download_music(url, music_id)`: 下载音乐文件
- `stream_download_and_play(url, music_id, callback)`: 流式下载播放
- `is_cached(music_id)`: 检查是否已缓存
- `clear_cache()`: 清理缓存

### 3. FavoriteManager (favorite_manager.py)

收藏管理器，管理用户的音乐收藏。

```python
from extra.music.api import FavoriteManager

manager = FavoriteManager()
manager.add_favorite(device_id, music_info)
```

**主要方法:**
- `add_favorite(device_id, music_info)`: 添加收藏
- `remove_favorite(device_id, music_id)`: 移除收藏
- `get_favorites(device_id)`: 获取收藏列表
- `search_favorites(device_id, keywords)`: 搜索收藏

## 使用方法

### 1. 基本播放

```python
from plugins_func.functions.online_music import online_music

# 播放指定音乐
result = online_music(conn, action="play", keywords="周杰伦 稻香")

# 搜索音乐
result = online_music(conn, action="search", keywords="流行音乐")
```

### 2. 收藏功能

```python
from plugins_func.functions.online_music import favorite_music

# 收藏当前播放的音乐
result = favorite_music(conn)

# 播放收藏的音乐
result = online_music(conn, action="play_favorite", keywords="周杰伦")
```

### 3. 播放控制

```python
from plugins_func.functions.online_music import next_music, stop_music

# 下一首
result = next_music(conn)

# 停止播放
result = stop_music(conn)
```

## 配置说明

### 1. API配置

音乐API的基础URL在 `MusicAPI` 类中配置：

```python
class MusicAPI:
    def __init__(self, base_url: str = "http://xn.xiaochun.cloud:10026"):
        self.base_url = base_url
```

### 2. 缓存配置

音乐缓存目录在 `MusicDownloader` 类中配置：

```python
class MusicDownloader:
    def __init__(self, cache_dir: str = "./data/music_cache"):
        self.cache_dir = Path(cache_dir)
```

### 3. 收藏配置

收藏数据文件在 `FavoriteManager` 类中配置：

```python
class FavoriteManager:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.favorites_file = self.data_dir / "music_favorites.yaml"
```

## 数据格式

### 音乐信息格式

```python
{
    "id": "歌曲ID",
    "name": "歌曲名称",
    "sq": 320,  # 音质等级
    "url": "歌曲下载地址",
    "try_listen": False,  # 是否是试听版本
    "duration": 180  # 歌曲时长（秒）
}
```

### 收藏数据格式

收藏数据以YAML格式存储在 `./data/music_favorites.yaml` 中：

```yaml
device_001:
  - id: "music_001"
    name: "稻香"
    sq: 320
    url: "http://example.com/daoxiang.mp3"
    try_listen: false
    duration: 180
  - id: "music_002"
    name: "青花瓷"
    sq: 320
    url: "http://example.com/qinghuaci.mp3"
    try_listen: false
    duration: 200
```

## 依赖要求

确保安装了以下依赖：

```bash
pip install aiohttp aiofiles requests pyyaml
```

## 注意事项

1. **网络连接**: 需要稳定的网络连接来搜索和下载音乐
2. **存储空间**: 音乐缓存会占用本地存储空间，定期清理缓存
3. **设备ID**: 每个设备都有独立的收藏列表，确保设备ID的唯一性
4. **API限制**: 注意音乐API的调用频率限制

## 故障排除

### 1. 搜索失败

- 检查网络连接
- 确认API地址是否正确
- 检查设备ID是否有效

### 2. 下载失败

- 检查音乐URL是否有效
- 确认缓存目录权限
- 检查磁盘空间是否充足

### 3. 播放失败

- 确认音频文件格式支持
- 检查TTS播放器配置
- 查看日志获取详细错误信息

## 开发计划

- [ ] 支持播放列表功能
- [ ] 添加音乐推荐算法
- [ ] 支持多音质选择
- [ ] 添加播放历史记录
- [ ] 支持歌词显示
- [ ] 添加音乐分类功能 