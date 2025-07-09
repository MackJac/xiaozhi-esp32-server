import random
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

class OnlineMusicStreamPlayer:
    def __init__(self):
        self._stream_started = False

    async def _play_audio_chunk(self, conn, chunk: bytes, temp_path: str):
        """播放音频数据块（流式播放）"""
        # 只负责推送TTS，文件写入由downloader负责
        if not self._stream_started:
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.FILE,
                    content_file=temp_path,
                )
            )
            self._stream_started = True

    def reset_stream(self):
        self._stream_started = False 