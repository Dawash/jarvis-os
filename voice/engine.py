"""
JARVIS-OS Voice Engine — Speech-to-Text and Text-to-Speech pipeline.
Handles wake word detection, continuous listening, and voice synthesis.
"""

import asyncio
import logging
import threading
import queue
from typing import Optional, Callable

logger = logging.getLogger("jarvis.voice")


class VoiceEngine:
    """
    Voice interface for JARVIS-OS.
    Supports wake-word activation, continuous listening, and speech synthesis.
    """

    def __init__(self, config: dict):
        self.config = config.get("voice", {})
        self.enabled = self.config.get("enabled", True)
        self.wake_word = self.config.get("wake_word", "jarvis").lower()
        self.stt_engine = self.config.get("stt_engine", "google")
        self.tts_engine_name = self.config.get("tts_engine", "pyttsx3")
        self.listen_timeout = self.config.get("listen_timeout", 10)

        self.kernel = None
        self.is_listening = False
        self._listen_thread = None
        self._command_queue = queue.Queue()
        self._on_command: Optional[Callable] = None

        # TTS engine
        self._tts = None
        self._tts_lock = threading.Lock()

        # STT engine
        self._recognizer = None
        self._microphone = None

    async def initialize(self, kernel):
        self.kernel = kernel
        self._init_tts()
        self._init_stt()
        logger.info(f"Voice Engine initialized — wake word: '{self.wake_word}'")

    def _init_tts(self):
        try:
            import pyttsx3
            self._tts = pyttsx3.init()
            rate = self.config.get("tts_rate", 180)
            self._tts.setProperty("rate", rate)
            # Try to set a natural voice
            voices = self._tts.getProperty("voices")
            if voices:
                for v in voices:
                    if "english" in v.name.lower():
                        self._tts.setProperty("voice", v.id)
                        break
            logger.info("TTS engine (pyttsx3) ready")
        except Exception as e:
            logger.warning(f"TTS initialization failed: {e} — voice output disabled")
            self._tts = None

    def _init_stt(self):
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = self.config.get("silence_threshold", 500)
            self._recognizer.dynamic_energy_threshold = True
            self._microphone = sr.Microphone
            logger.info("STT engine ready")
        except Exception as e:
            logger.warning(f"STT initialization failed: {e} — voice input disabled")
            self._recognizer = None

    async def shutdown(self):
        self.stop_listening()

    # ── Text-to-Speech ───────────────────────────────────────────

    def speak(self, text: str):
        """Speak text aloud using TTS engine."""
        if not self._tts:
            logger.debug(f"TTS not available, skipping: {text[:100]}")
            return

        def _speak():
            with self._tts_lock:
                try:
                    self._tts.say(text)
                    self._tts.runAndWait()
                except Exception as e:
                    logger.error(f"TTS error: {e}")

        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()

    async def speak_async(self, text: str):
        """Async wrapper for speak."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.speak, text)

        # Also broadcast to dashboard
        if self.kernel:
            from core.kernel import Event
            await self.kernel.emit_event(Event("voice.speak", {"text": text}))

    # ── Speech-to-Text ───────────────────────────────────────────

    def start_listening(self, on_command: Callable = None):
        """Start continuous voice listening in background thread."""
        if not self._recognizer:
            logger.warning("STT not available — cannot start listening")
            return

        self._on_command = on_command
        self.is_listening = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        logger.info("Voice listening started")

    def stop_listening(self):
        """Stop voice listening."""
        self.is_listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
        logger.info("Voice listening stopped")

    def _listen_loop(self):
        """Background listening loop — wake word detection + command capture."""
        import speech_recognition as sr

        while self.is_listening:
            try:
                with self._microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    logger.debug("Listening...")
                    audio = self._recognizer.listen(source, timeout=self.listen_timeout, phrase_time_limit=15)

                # Recognize speech
                text = self._recognize_audio(audio)
                if not text:
                    continue

                text_lower = text.lower().strip()
                logger.info(f"Heard: {text}")

                # Check for wake word
                if self.wake_word in text_lower:
                    # Extract the command after the wake word
                    idx = text_lower.index(self.wake_word) + len(self.wake_word)
                    command = text[idx:].strip().lstrip(",").strip()

                    if command:
                        logger.info(f"Voice command: {command}")
                        self._command_queue.put(command)
                        if self._on_command:
                            self._on_command(command)
                    else:
                        # Wake word only — listen for the next phrase as command
                        logger.info("Wake word detected — listening for command...")
                        try:
                            with self._microphone() as source:
                                audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=15)
                            command = self._recognize_audio(audio)
                            if command:
                                logger.info(f"Voice command: {command}")
                                self._command_queue.put(command)
                                if self._on_command:
                                    self._on_command(command)
                        except Exception:
                            pass

            except Exception as e:
                if "timed out" not in str(e).lower():
                    logger.debug(f"Listen error: {e}")

    def _recognize_audio(self, audio) -> Optional[str]:
        """Convert audio to text using configured STT engine."""
        try:
            if self.stt_engine == "google":
                return self._recognizer.recognize_google(audio)
            elif self.stt_engine == "whisper":
                return self._recognizer.recognize_whisper(audio, model="base")
            else:
                return self._recognizer.recognize_google(audio)
        except Exception:
            return None

    def get_pending_command(self) -> Optional[str]:
        """Get the next pending voice command."""
        try:
            return self._command_queue.get_nowait()
        except queue.Empty:
            return None

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "listening": self.is_listening,
            "wake_word": self.wake_word,
            "stt_engine": self.stt_engine,
            "tts_engine": self.tts_engine_name,
            "tts_available": self._tts is not None,
            "stt_available": self._recognizer is not None,
        }
