"""
Simple test view to verify OpenAI API connectivity on DigitalOcean
"""
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def test_openai_api(request):
    """Test OpenAI API connection"""
    try:
        # Check if API key is loaded
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        
        if not api_key:
            return JsonResponse({
                'success': False,
                'message': 'OpenAI API key not found in settings'
            }, status=500)
        
        # Test API connection
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': 'Say "Hello from DigitalOcean!"'}],
            max_tokens=20
        )
        
        return JsonResponse({
            'success': True,
            'message': 'OpenAI API connection successful!',
            'api_key_prefix': f'{api_key[:20]}...{api_key[-4:]}',
            'response': response.choices[0].message.content,
            'model': response.model,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'OpenAI API connection failed: {str(e)}',
            'error_type': type(e).__name__
        }, status=500)
