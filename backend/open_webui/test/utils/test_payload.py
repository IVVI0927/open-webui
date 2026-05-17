import sys
import types

_env = types.ModuleType('open_webui.env')
_env.CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE = 16384
sys.modules.setdefault('open_webui.env', _env)
sys.modules.setdefault('mimeparse', types.ModuleType('mimeparse'))
sys.modules.setdefault('aiohttp', types.ModuleType('aiohttp'))

_task = types.ModuleType('open_webui.utils.task')
_task.prompt_template = None
_task.prompt_variables_template = None
sys.modules.setdefault('open_webui.utils.task', _task)

from open_webui.utils.payload import convert_messages_openai_to_ollama  # noqa: E402


def test_convert_messages_openai_to_ollama_preserves_text_and_base64_image():
    messages = [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'Describe this image.'},
                {
                    'type': 'image_url',
                    'image_url': {'url': 'data:image/png;base64,aGVsbG8='},
                },
            ],
        }
    ]

    result = convert_messages_openai_to_ollama(messages)

    assert result == [
        {
            'role': 'user',
            'content': 'Describe this image.',
            'images': ['aGVsbG8='],
        }
    ]
