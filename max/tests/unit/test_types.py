"""Unit tests for type models."""

from __future__ import annotations

import pydantic_core
import pytest
from maxpy.types import (
    Message, Chat, User, Photo, Video, Voice, VideoNote, Document,
    PhotoAttachment, VideoAttachment, AttachmentUnion,
)
from maxpy.enums import ChatType, MessageType
from maxpy.exceptions import FileValidationError


class TestMessage:
    """Tests for Message model."""

    def test_create_text_message(self):
        msg = Message(
            id="msg_1",
            chat_id="chat_1",
            sender_id="user_1",
            text="Hello world",
            created_at=1234567890,
        )
        assert msg.text == "Hello world"
        assert msg.type == MessageType.TEXT
        assert not msg.has_media

    def test_create_message_with_photo(self):
        photo = Photo(path="test.jpg")
        attachment = PhotoAttachment(photo=photo)
        msg = Message(
            id="msg_2",
            chat_id="chat_1",
            sender_id="user_1",
            text="Nice photo!",
            attachments=[attachment],
            created_at=1234567890,
        )
        assert msg.has_media
        assert msg.photo is not None
        assert msg.photo.name == "test.jpg"

    def test_message_properties(self):
        photo = Photo(path="test.jpg")
        video = Video(path="test.mp4")
        msg = Message(
            id="msg_3",
            chat_id="chat_1",
            sender_id="user_1",
            attachments=[
                PhotoAttachment(photo=photo),
                VideoAttachment(video=video),
            ],
            created_at=1234567890,
        )
        assert msg.photo is not None
        assert msg.video is not None
        assert msg.voice is None
        assert msg.video_note is None
        assert msg.document is None

    def test_attachment_union(self):
        photo = Photo(path="test.jpg")
        attachment = PhotoAttachment(photo=photo)
        assert isinstance(attachment, AttachmentUnion)


class TestChat:
    """Tests for Chat model."""

    def test_create_private_chat(self):
        chat = Chat(
            id="user_1_user_2",
            type=ChatType.PRIVATE,
        )
        assert chat.is_private
        assert not chat.is_group
        assert not chat.is_channel

    def test_create_group_chat(self):
        chat = Chat(
            id="group_1",
            type=ChatType.GROUP,
            title="Test Group",
            members_count=5,
        )
        assert chat.is_group
        assert not chat.is_private
        assert not chat.is_channel
        assert chat.title == "Test Group"

    def test_create_channel(self):
        chat = Chat(
            id="channel_1",
            type=ChatType.CHANNEL,
            title="Test Channel",
            members_count=100,
        )
        assert chat.is_channel
        assert not chat.is_private
        assert not chat.is_group


class TestUser:
    """Tests for User model."""

    def test_get_full_name(self):
        user = User(
            id="user_1",
            first_name="John",
            last_name="Doe",
        )
        assert user.get_full_name() == "John Doe"

    def test_get_full_name_no_names(self):
        user = User(
            id="user_1",
            username="johndoe",
        )
        assert user.get_full_name() == "johndoe"

    def test_get_chat_id(self):
        user = User(id="user_1")
        chat_id = user.get_chat_id("user_2")
        assert chat_id == "user_1_user_2"  # Sorted

    def test_get_chat_id_reverse(self):
        user = User(id="user_2")
        chat_id = user.get_chat_id("user_1")
        assert chat_id == "user_1_user_2"  # Sorted


class TestPhoto:
    """Tests for Photo file model."""

    def test_photo_validation(self):
        photo = Photo(path="test.jpg")
        ext, mime = photo.validate_extension({"jpg", "jpeg", "png"})
        assert ext == "jpg"
        assert mime == "image/jpeg"

    def test_photo_invalid_extension(self):
        with pytest.raises(pydantic_core.ValidationError):
            Photo(path="test.txt")

    def test_photo_mime_type_guess(self):
        photo = Photo(path="test.png")
        assert photo.mime_type == "image/png"


class TestVideo:
    """Tests for Video file model."""

    def test_video_validation(self):
        video = Video(path="test.mp4")
        ext, mime = video.validate_extension({"mp4", "mov", "mkv"})
        assert ext == "mp4"
        assert mime == "video/mp4"

    def test_video_invalid_extension(self):
        with pytest.raises(pydantic_core.ValidationError):
            Video(path="test.txt")


class TestVoice:
    """Tests for Voice file model."""

    def test_voice_validation(self):
        voice = Voice(path="test.ogg")
        ext, mime = voice.validate_extension({"ogg", "opus", "mp3"})
        assert ext == "ogg"
        assert mime == "audio/ogg"


class TestVideoNote:
    """Tests for VideoNote file model."""

    def test_video_note_validation(self):
        vn = VideoNote(path="test.mp4")
        ext, mime = vn.validate_extension({"mp4", "mov"})
        assert ext == "mp4"
        assert mime == "video/mp4"


class TestDocument:
    """Tests for Document file model."""

    def test_document_creation(self):
        doc = Document(path="test.pdf")
        assert doc.name == "test.pdf"
        assert doc.mime_type == "application/pdf"