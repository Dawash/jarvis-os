"""
JARVIS-OS Voice Engine — Interruptible TTS with barge-in and mic echo suppression.

Features:
- Interruptible TTS: user can interrupt JARVIS mid-sentence via barge-in
- edge-tts support: Microsoft Neural TTS (free, high-quality) with pyttsx3 fallback
- Mic muting during TTS: prevents echo feedback loop
- Sentence-level chunking: TTS checks for interrupts between sentences
- Dual activation: wake word + hotkey support
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import queue
from typing import Optional, Callable

logger = logging.getLogger("jarvis.voice")


class VoiceEngine:
    """
    Voice interface for JARVIS-OS.
    Supports interruptible TTS, wake-word activation, and barge-in.
    """

    def __init__(self, config: dict):
        self.config = config.get("voice", {})
        self.enabled = self.config.get("enabled", True)
        self.wake_word = self.config.get("wake_word", "jarvis").lower()
        self.stt_engine = self.config.get("stt_engine", "google")
        self.tts_engine_name = self.config.get("tts_engine", "edge-tts")
        self.tts_voice = self.config.get("tts_voice", "en-US-GuyNeural")
        self.listen_timeout = self.config.get("listen_timeout", 10)

        self.kernel = None
        self.is_listening = False
        self._listen_thread = None
        self._command_queue = queue.Queue()
        self._on_command: Optional[Callable] = None

        # TTS state
        self._tts = None
        self._tts_lock = threading.Lock()
        self._is_speaking = False
        self._stop_speaking = threading.Event()  # Signal to interrupt TTS
        self._playback_process: Optional[subprocess.Popen] = None  # Audio player subprocess

        # edge-tts availability
        self._edge_tts_available = False

        # Audio player command (mpv > ffplay > aplay)
        self._audio_player = None

        # STT engine
        self._recognizer = None
        self._microphone = None

    async def initialize(self, kernel):
        self.kernel = kernel
        self._detect_audio_player()
        self._init_tts()
        self._init_stt()
        logger.info(
            f"Voice Engine initialized — wake word: '{self.wake_word}', "
            f"TTS: {self.tts_engine_name}, barge-in: enabled"
        )

    def _detect_audio_player(self):
        """Find the best available audio player for TTS playback."""
        for player in ["mpv", "ffplay", "aplay", "paplay"]:
            if shutil.which(player):
                self._audio_player = player
                logger.info(f"Audio player: {player}")
                return
        logger.warning("No audio player found (mpv/ffplay/aplay) — file-based TTS may not play")

    def _init_tts(self):
        # Try edge-tts first (high-quality neural voices)
        if self.tts_engine_name in ("edge-tts", "edge"):
            try:
                import edge_tts  # noqa: F401
                self._edge_tts_available = True
                self.tts_engine_name = "edge-tts"
                logger.info(f"TTS engine: edge-tts (voice: {self.tts_voice})")
                return
            except ImportError:
                logger.info("edge-tts not installed, falling back to pyttsx3")

        # Fallback to pyttsx3
        try:
            import pyttsx3
            self._tts = pyttsx3.init()
            rate = self.config.get("tts_rate", 180)
            self._tts.setProperty("rate", rate)
            voices = self._tts.getProperty("voices")
            if voices:
                for v in voices:
                    if "english" in v.name.lower():
                        self._tts.setProperty("voice", v.id)
                        break
            self.tts_engine_name = "pyttsx3"
            logger.info("TTS engine: pyttsx3")
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
        self.barge_in()  # Stop any ongoing speech
        self.stop_listening()

    # ── Text-to-Speech (Interruptible) ─────────────────────────

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentence chunks for interruptible playback."""
        # Split on sentence boundaries but keep reasonable chunk sizes
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Merge very short sentences together
        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) < 200:
                current = f"{current} {s}".strip() if current else s
            else:
                if current:
                    chunks.append(current)
                current = s
        if current:
            chunks.append(current)
        return chunks if chunks else [text]

    def speak(self, text: str):
        """Speak text aloud with barge-in support. Non-blocking."""
        if not self._tts and not self._edge_tts_available:
            logger.debug(f"TTS not available, skipping: {text[:100]}")
            return

        self._stop_speaking.clear()

        def _speak():
            self._is_speaking = True
            try:
                if self._edge_tts_available:
                    self._speak_edge_tts(text)
                else:
                    self._speak_pyttsx3(text)
            finally:
                self._is_speaking = False
                self._stop_speaking.clear()

        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()

    def _speak_edge_tts(self, text: str):
        """Speak using edge-tts with sentence-level interruption."""
        chunks = self._split_sentences(text)

        for chunk in chunks:
            if self._stop_speaking.is_set():
                logger.info("TTS interrupted (barge-in) between sentences")
                return

            tmp_file = None
            try:
                # Generate audio for this chunk
                tmp_fd, tmp_file = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_tts_")
                os.close(tmp_fd)

                # Run edge-tts synchronously (it has its own async, but we're in a thread)
                import edge_tts
                loop = asyncio.new_event_loop()
                communicate = edge_tts.Communicate(chunk, self.tts_voice)
                loop.run_until_complete(communicate.save(tmp_file))
                loop.close()

                if self._stop_speaking.is_set():
                    return

                # Play the audio file
                self._play_audio_file(tmp_file)

            except Exception as e:
                logger.error(f"edge-tts error: {e}")
                # Fallback to pyttsx3 for this chunk if available
                if self._tts:
                    self._speak_pyttsx3_chunk(chunk)
            finally:
                if tmp_file and os.path.exists(tmp_file):
                    try:
                        os.unlink(tmp_file)
                    except OSError:
                        pass

    def _play_audio_file(self, filepath: str):
        """Play an audio file with a subprocess, interruptible."""
        if not self._audio_player:
            return

        try:
            cmd = {
                "mpv": ["mpv", "--no-terminal", "--no-video", filepath],
                "ffplay": ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", filepath],
                "aplay": ["aplay", filepath],
                "paplay": ["paplay", filepath],
            }.get(self._audio_player, [self._audio_player, filepath])

            self._playback_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait for playback to finish, checking for interrupts
            while self._playback_process.poll() is None:
                if self._stop_speaking.is_set():
                    self._playback_process.terminate()
                    try:
                        self._playback_process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        self._playback_process.kill()
                    logger.info("TTS playback interrupted (barge-in)")
                    return
                self._stop_speaking.wait(timeout=0.1)

        except Exception as e:
            logger.error(f"Audio playback error: {e}")
        finally:
            self._playback_process = None

    def _speak_pyttsx3(self, text: str):
        """Speak using pyttsx3 with sentence-level interruption."""
        chunks = self._split_sentences(text)
        for chunk in chunks:
            if self._stop_speaking.is_set():
                logger.info("TTS interrupted (barge-in)")
                return
            self._speak_pyttsx3_chunk(chunk)

    def _speak_pyttsx3_chunk(self, text: str):
        """Speak a single chunk with pyttsx3."""
        with self._tts_lock:
            try:
                self._tts.say(text)
                self._tts.runAndWait()
            except Exception as e:
                logger.error(f"TTS error: {e}")

    async def speak_async(self, text: str):
        """Async wrapper for speak with dashboard broadcast."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.speak, text)

        # Broadcast to dashboard for browser-side TTS
        if self.kernel:
            from core.kernel import Event
            await self.kernel.emit_event(Event("voice.speak", {"text": text}))

    def barge_in(self):
        """
        Interrupt TTS immediately. Called when:
        - User starts speaking (voice activity detected)
        - User presses a key/clicks interrupt button
        - A new command arrives while JARVIS is still talking
        """
        if not self._is_speaking:
            return

        logger.info("Barge-in triggered — stopping TTS")
        self._stop_speaking.set()

        # Kill active playback subprocess immediately
        if self._playback_process and self._playback_process.poll() is None:
            try:
                self._playback_process.terminate()
            except Exception:
                pass

        # Stop pyttsx3 if it's the active engine
        if self._tts:
            try:
                self._tts.stop()
            except Exception:
                pass

        # Broadcast interrupt event to dashboard
        if self.kernel:
            try:
                asyncio.get_event_loop().create_task(
                    self.kernel.emit_event(
                        __import__("core.kernel", fromlist=["Event"]).Event(
                            "voice.interrupted", {}
                        )
                    )
                )
            except RuntimeError:
                pass  # No event loop running (called from sync context)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    # ── Speech-to-Text (with echo suppression) ──────────────────

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
        """Background listening loop with mic muting during TTS."""
        import speech_recognition as sr

        while self.is_listening:
            # Mic echo suppression: skip listening while JARVIS is speaking
            if self._is_speaking:
                self._stop_speaking.wait(timeout=0.3)
                continue

            try:
                with self._microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    logger.debug("Listening...")
                    audio = self._recognizer.listen(
                        source, timeout=self.listen_timeout, phrase_time_limit=15
                    )

                # If JARVIS started speaking while we were recording, trigger barge-in
                if self._is_speaking:
                    self.barge_in()

                # Recognize speech
                text = self._recognize_audio(audio)
                if not text:
                    continue

                text_lower = text.lower().strip()
                logger.info(f"Heard: {text}")

                # If JARVIS is speaking, any recognized speech triggers barge-in
                if self._is_speaking:
                    self.barge_in()

                # Check for wake word
                if self.wake_word in text_lower:
                    # Extract the command after the wake word
                    idx = text_lower.index(self.wake_word) + len(self.wake_word)
                    command = text[idx:].strip().lstrip(",").strip()

                    if command:
                        self._dispatch_command(command)
                    else:
                        # Wake word only — listen for the next phrase as command
                        logger.info("Wake word detected — listening for command...")
                        self._emit_event_sync("voice.wake_word", {})
                        try:
                            with self._microphone() as source:
                                audio = self._recognizer.listen(
                                    source, timeout=5, phrase_time_limit=15
                                )
                            command = self._recognize_audio(audio)
                            if command:
                                self._dispatch_command(command)
                        except Exception:
                            pass

            except Exception as e:
                if "timed out" not in str(e).lower():
                    logger.debug(f"Listen error: {e}")

    def _dispatch_command(self, command: str):
        """Route a recognized voice command."""
        logger.info(f"Voice command: {command}")

        # Interrupt TTS if JARVIS is currently speaking
        if self._is_speaking:
            self.barge_in()

        self._command_queue.put(command)
        if self._on_command:
            self._on_command(command)

        # Broadcast to dashboard
        self._emit_event_sync("voice.command", {"command": command})

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

    def _emit_event_sync(self, event_type: str, data: dict):
        """Emit a kernel event from a sync context (listener thread)."""
        if not self.kernel:
            return
        try:
            from core.kernel import Event
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.kernel.emit_event(Event(event_type, data)), loop
                )
        except RuntimeError:
            pass

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
            "speaking": self._is_speaking,
            "wake_word": self.wake_word,
            "stt_engine": self.stt_engine,
            "tts_engine": self.tts_engine_name,
            "tts_voice": self.tts_voice,
            "tts_available": self._tts is not None or self._edge_tts_available,
            "stt_available": self._recognizer is not None,
            "barge_in_enabled": True,
        }
