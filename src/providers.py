"""
🔌 MULTI-PROVIDER LLM ADAPTER (Groq, OpenAI, Gemini, Anthropic, OpenRouter & Offline Mock)
Hỗ trợ chuyển đổi linh hoạt giữa các nhà cung cấp AI chỉ bằng cách đổi biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho tất cả các LLM Provider"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class GroqProvider(BaseLLMProvider):
    """Groq Provider sử dụng API tương thích OpenAI."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "llama-3.3-70b-versatile"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_groq_api_key_here":
            return "[Groq Error]: Chưa cấu hình GROQ_API_KEY trong file .env!"

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "messages": messages,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]

            return f"[Groq API Error {response.status_code}]: {response.text}"
        except requests.RequestException as e:
            return f"[Groq Connection Error]: {str(e)}"
        except (KeyError, IndexError, TypeError, ValueError) as e:
            return f"[Groq Response Error]: Phản hồi API không hợp lệ ({str(e)})"


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        # Dùng alias ổn định để tự trỏ tới bản Flash hiện hành, tránh lỗi khi
        # một model version cũ bị Google ngừng cấp cho người dùng mới.
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-flash-latest"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env!"
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (GPT-4o, GPT-3.5-turbo, etc.)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env!"
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            if e.__class__.__name__ == "AuthenticationError":
                # Không đưa exception gốc ra console vì có thể chứa một phần
                # API key hoặc thông tin xác thực nhạy cảm.
                return (
                    "[OpenAI Error]: OPENAI_API_KEY không hợp lệ hoặc đã bị thu hồi. "
                    "Hãy tạo key mới và cập nhật file .env."
                )
            return f"[OpenAI Exception]: {str(e)}"


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider (Claude 3.5 Sonnet, Claude 3 Haiku)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "claude-3-haiku-20240307"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_anthropic_api_key_here":
            return "[Anthropic Error]: Chưa cấu hình ANTHROPIC_API_KEY trong file .env!"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = {
                "model": self.model_name,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
                
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Anthropic Exception]: {str(e)}"


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter Provider (Hỗ trợ gọi mọi model qua OpenRouter API)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "google/gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            return "[OpenRouter Error]: Chưa cấu hình OPENROUTER_API_KEY trong file .env!"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model_name,
                "messages": messages
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[OpenRouter API Error {res.status_code}]: {res.text}"
        except Exception as e:
            return f"[OpenRouter Exception]: {str(e)}"


class MockProvider(BaseLLMProvider):
    """Offline Mock Provider (Cho bài test không cần kết nối API)"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        text = prompt.lower()
        if "không có công cụ tìm kiếm" in system_prompt.lower():
            if "đăng nhập trái phép" in text:
                return (
                    "Tôi không thể truy cập tài khoản hoặc tin nhắn riêng tư. "
                    "Bạn có thể hỏi trực tiếp về sở thích với sự đồng ý của người nhận."
                )
            if "cuối tuần này" in text:
                return (
                    "Bạn cho tôi biết thêm độ tuổi, mối quan hệ, sở thích, tính cách, "
                    "ngân sách và điều người nhận không thích nhé."
                )
            if "đồng nghiệp" in text:
                return (
                    "Ba gợi ý trong khoảng 300.000 đồng: 1) cà phê rang xay 150.000 đồng, "
                    "đúng sở thích; 2) phin pha cà phê 120.000 đồng, dùng hằng ngày; "
                    "3) cốc giữ nhiệt 280.000 đồng, tiện mang đi làm. Giá và khả năng "
                    "mua chỉ là ước tính."
                )
            return (
                "Tôi có thể gợi ý quà theo thông tin đã cho, nhưng giá và khả năng mua "
                "chỉ là ước tính vì tôi không có dữ liệu cửa hàng theo thời gian thực."
            )

        if "đăng nhập trái phép" in text:
            return (
                "Thought: Yêu cầu vi phạm quyền riêng tư nên cần từ chối.\n"
                "Final Answer: Tôi không thể truy cập trái phép hoặc nhận mật khẩu. "
                "Hãy hỏi sở thích của người nhận với sự đồng ý của họ."
            )
        if "cuối tuần này" in text:
            return (
                "Thought: Tôi cần thêm thông tin trước khi sử dụng công cụ.\n"
                "Final Answer: Bạn cho tôi biết độ tuổi, sở thích, tính cách, ngân sách "
                "và điều người nhận không thích nhé."
            )
        if "đồng nghiệp" in text:
            return (
                "Thought: Câu hỏi đơn giản có thể trả lời trực tiếp.\n"
                "Final Answer: Ba gợi ý trong khoảng 300.000 đồng: 1) cà phê rang xay "
                "150.000 đồng, đúng sở thích; 2) phin pha cà phê 120.000 đồng, dùng "
                "hằng ngày; 3) cốc giữ nhiệt 280.000 đồng, tiện mang đi làm. Giá cần "
                "được xác minh khi mua."
            )

        if "bố tôi" in text:
            if "observation:" not in text:
                return (
                    "Thought: Lưu hồ sơ người nhận.\n"
                    'Action: save_recipient_profile["Bố", "thực tế", "chăm sóc cây", "1000000"]'
                )
            if "tìm thấy" not in text:
                return 'Thought: Tìm các món phù hợp.\nAction: search_gifts["Bố"]'
            detail_count = text.count("mô tả:")
            if detail_count == 0:
                return 'Thought: Kiểm tra lựa chọn thực tế nhất.\nAction: get_gift_details["G16", "Bố"]'
            if detail_count == 1:
                return 'Thought: Kiểm tra lựa chọn thứ hai.\nAction: get_gift_details["G15", "Bố"]'
            if detail_count == 2:
                return 'Thought: Kiểm tra lựa chọn thứ ba.\nAction: get_gift_details["G10", "Bố"]'
            if "đã chốt danh sách" not in text:
                return 'Thought: Chốt món phù hợp nhất.\nAction: save_shortlist["Bố", "G16"]'
            return (
                "Thought: Đã đủ thông tin.\n"
                "Final Answer: Xếp hạng: 1) G16 máy đo độ ẩm đất, 330.000 VNĐ; "
                "2) G15 bộ dụng cụ chăm cây, 460.000 VNĐ; 3) G10 kéo cắt tỉa, "
                "150.000 VNĐ. G16 phù hợp nhất vì thiết thực, hỗ trợ chăm cây và "
                "không mang tính trang trí."
            )

        if "bạn gái tôi" in text:
            if "observation:" not in text:
                return (
                    "Thought: Lưu hồ sơ người nhận.\n"
                    'Action: save_recipient_profile["Bạn gái", "hướng nội", '
                    '"đọc sách, quan tâm môi trường", "800000"]'
                )
            if "tìm thấy" not in text:
                return 'Thought: Tìm các món phù hợp.\nAction: search_gifts["Bạn gái"]'
            detail_count = text.count("mô tả:")
            if detail_count == 0:
                return 'Thought: Kiểm tra lựa chọn thân thiện môi trường.\nAction: get_gift_details["G17", "Bạn gái"]'
            if detail_count == 1:
                return 'Thought: Kiểm tra lựa chọn thứ hai.\nAction: get_gift_details["G02", "Bạn gái"]'
            if detail_count == 2:
                return 'Thought: Kiểm tra lựa chọn thứ ba.\nAction: get_gift_details["G01", "Bạn gái"]'
            if "đã chốt danh sách" not in text:
                return 'Thought: Chốt món phù hợp nhất.\nAction: save_shortlist["Bạn gái", "G17"]'
            return (
                "Thought: Đã đủ thông tin.\n"
                "Final Answer: Xếp hạng: 1) G17 sổ đọc sách giấy tái chế, 210.000 VNĐ; "
                "2) G02 đèn đọc sách, 250.000 VNĐ; 3) G01 combo tiểu thuyết, "
                "420.000 VNĐ. G17 phù hợp nhất vì tối giản, không mùi và sử dụng "
                "giấy tái chế."
            )

        return (
            "Thought: Tôi cần thêm thông tin trước khi sử dụng công cụ.\n"
            "Final Answer: Hãy cung cấp tên, sở thích và ngân sách của người nhận."
        )


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """Factory function tự chọn Provider từ biến môi trường LLM_PROVIDER"""
    name = (provider_name or os.getenv("LLM_PROVIDER") or "mock").lower().strip()
    
    if name == "groq":
        return GroqProvider()
    elif name == "gemini":
        return GeminiProvider()
    elif name == "openai":
        return OpenAIProvider()
    elif name == "anthropic":
        return AnthropicProvider()
    elif name == "openrouter":
        return OpenRouterProvider()
    else:
        return MockProvider()


if __name__ == "__main__":
    print("=== TEST MULTI-PROVIDER LLM ADAPTER ===")
    provider = get_llm_provider()
    print(f"✅ Provider đang dùng: {provider.__class__.__name__}")
    print(f"🤖 User Query: Hello")
    print(f"💬 Response  : {provider.generate('Hello')}")
