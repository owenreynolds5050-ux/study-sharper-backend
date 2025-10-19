# app/services/audio_transcription.py
import io
import tempfile
import os
from faster_whisper import WhisperModel

# Initialize Whisper model (using faster-whisper for better performance)
# Model is loaded once and reused
_whisper_model = None

def get_whisper_model():
    """Get or initialize Whisper model (singleton pattern)"""
    global _whisper_model
    
    if _whisper_model is None:
        # Use 'base' model - good balance of speed and accuracy
        # Options: tiny, base, small, medium, large
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        print("✓ Whisper model loaded")
    
    return _whisper_model

async def transcribe_audio(audio_data: bytes) -> str:
    """
    Transcribe audio file to text using Whisper.
    
    Args:
        audio_data: Raw audio file bytes
        
    Returns:
        Transcribed text as markdown
    """
    
    # Save to temporary file (Whisper needs file path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".audio") as temp_file:
        temp_file.write(audio_data)
        temp_path = temp_file.name
    
    try:
        model = get_whisper_model()
        
        # Transcribe
        segments, info = model.transcribe(
            temp_path,
            beam_size=5,
            language=None,  # Auto-detect language
            vad_filter=True,  # Voice activity detection
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        # Combine segments into full transcript
        transcript_parts = []
        
        for segment in segments:
            transcript_parts.append(segment.text.strip())
        
        transcript = " ".join(transcript_parts)
        
        # Format as markdown
        formatted = f"# Audio Transcript\n\n{transcript}\n\n---\n\n*Transcribed using Whisper (Language: {info.language})*"
        
        return formatted
        
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except Exception:
            pass
