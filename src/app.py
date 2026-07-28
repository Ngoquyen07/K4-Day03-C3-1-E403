"""
🚀 CORE AGENT APP (Dành cho Role 4: Core Agent Developer)
File chính ghép nối tất cả các thành phần: Tools + Prompts + Test Cases + Multi-Provider.
"""

import json
import os
import re
import sys
from ast import literal_eval
from inspect import signature
from dotenv import load_dotenv

# Đảm bảo import các module cùng thư mục src/ hoạt động mượt mà
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import các thành phần từ file của Role 2, Role 3 & Multi-Provider Adapter
from tools import AVAILABLE_TOOLS, reset_session
from prompts import CHATBOT_BASELINE_PROMPT, REACT_SYSTEM_PROMPT, MAX_ITERATIONS
from providers import get_llm_provider

load_dotenv()


PRIVACY_ATTACK_PATTERNS = (
    "đăng nhập trái phép",
    "đọc tin nhắn riêng",
    "mật khẩu",
    "password",
)


def load_test_cases():
    """Đọc bộ test cases từ config/test_cases.json của Role 1"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    
    # Fallback kiểm tra nếu file ở thư mục hiện tại
    if not os.path.exists(config_path):
        config_path = "test_cases.json"
        
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_baseline_chatbot(user_query: str, provider):
    """
    Chạy đúng một lượt Chatbot gốc (Baseline), không gọi công cụ.

    Trả về raw response để Role 5 có thể lưu và đánh giá kết quả.
    """
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    print(f"⚙️ System Prompt: {CHATBOT_BASELINE_PROMPT.strip()}")
    
    # Gọi LLM Provider thực hiện sinh câu trả lời
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot trả lời:\n{response}")
    return response


def print_react_step(step: int, thought: str, action: str, observation: str):
    """In đầy đủ một bước Thought -> Action -> Observation theo Markdown."""
    print(f"* **Thought {step}**: {thought}")
    print(f"* **Action {step}**: `{action}`")

    observation = str(observation)
    if "\n" not in observation:
        print(f"* **Observation {step}**: `{observation}`")
        return

    print(f"* **Observation {step}**:")
    print("  ```text")
    for line in observation.splitlines():
        print(f"  {line}")
    print("  ```")


def run_react_agent(user_query: str, provider):
    """
    Chạy vòng lặp Thought -> Action -> Observation cho đến Final Answer.

    Mỗi vòng chỉ cho phép một Action, chỉ gọi tool trong registry và đưa
    Observation thật trở lại ngữ cảnh LLM. Hàm trả về Final Answer hoặc
    safe fallback khi chạm guardrail.
    """
    print("\n### 🧠 ReAct Agent:")
    reset_session()

    # Lớp chặn nhanh; system prompt tiếp tục xử lý các cách diễn đạt khác.
    if any(pattern in user_query.casefold() for pattern in PRIVACY_ATTACK_PATTERNS):
        answer = (
            "Tôi không thể truy cập trái phép, đọc tin nhắn riêng hoặc tiếp nhận mật khẩu. "
            "Hãy hỏi sở thích của người nhận với sự đồng ý của họ."
        )
        print("* **Thought 1**: Yêu cầu có dấu hiệu xâm phạm quyền riêng tư nên cần từ chối.")
        print(f'- **Final Answer**: *"{answer}"*')
        return answer

    trace = []
    executed_actions = set()

    for step in range(1, MAX_ITERATIONS + 1):
        context = [f"User Goal: {user_query}"]
        if trace:
            context.append("Trace đã được hệ thống xác thực:")
            context.extend(trace)
        context.append("Hãy đưa ra đúng một bước tiếp theo theo định dạng bắt buộc.")

        llm_output = provider.generate(
            "\n\n".join(context),
            system_prompt=REACT_SYSTEM_PROMPT,
        ).strip()

        thought_match = re.search(r"^Thought:\s*(.+)$", llm_output, flags=re.MULTILINE)
        thought = thought_match.group(1).strip() if thought_match else "Phân tích bước tiếp theo."

        if re.match(r"^\[[^\]]+(?:Error|Exception)[^\]]*\]:", llm_output):
            fallback = "Xin lỗi, dịch vụ LLM đang gặp lỗi nên tôi chưa thể tiếp tục tư vấn."
            print(f"* **Thought {step}**: Dịch vụ LLM trả về lỗi, cần dừng vòng lặp an toàn.")
            print(f'- **Final Answer**: *"{fallback}"*')
            return fallback

        final_match = re.search(
            r"^Final Answer:\s*(.+)$", llm_output, flags=re.MULTILINE | re.DOTALL
        )
        action_lines = re.findall(r"^Action:\s*(.+)$", llm_output, flags=re.MULTILINE)
        if final_match and not action_lines:
            final_answer = final_match.group(1).strip()
            print(f"* **Thought {step}**: {thought}")
            print(f'- **Final Answer**: *"{final_answer}"*')
            return final_answer

        if final_match or len(action_lines) != 1:
            observation = (
                "LỖI: Phản hồi phải chứa đúng một Action hoặc một Final Answer. "
                "Hãy sửa đúng định dạng."
            )
            print_react_step(
                step, thought, "Phản hồi không có đúng một Action", observation
            )
            trace.extend([llm_output, f"Observation: {observation}"])
            continue

        action_text = action_lines[0].strip()
        action_match = re.fullmatch(r"([A-Za-z_]\w*)\s*(\[.*\])", action_text)
        if not action_match:
            observation = (
                "LỖI: Action sai cú pháp. Dùng tên_tool[\"tham số 1\", \"tham số 2\"]."
            )
            print_react_step(step, thought, action_text, observation)
            trace.extend([llm_output, f"Observation: {observation}"])
            continue

        tool_name, raw_args = action_match.groups()
        tool = AVAILABLE_TOOLS.get(tool_name)
        if tool is None:
            observation = (
                f"LỖI: Tool '{tool_name}' không tồn tại. Tool hợp lệ: "
                f"{', '.join(AVAILABLE_TOOLS)}."
            )
        else:
            try:
                parsed_args = literal_eval(raw_args)
                if not isinstance(parsed_args, list):
                    raise ValueError("Danh sách tham số phải đặt trong dấu [].")
                args = [str(value) for value in parsed_args]
                signature(tool).bind(*args)

                action_key = (tool_name, tuple(args))
                if action_key in executed_actions:
                    observation = (
                        "LỖI: Action này đã được thực thi trước đó. "
                        "Không lặp lại cùng tool và tham số."
                    )
                else:
                    executed_actions.add(action_key)
                    observation = tool(*args)
            except (SyntaxError, ValueError, TypeError) as exc:
                observation = f"LỖI: Tham số của {tool_name} không hợp lệ: {exc}"
            except Exception as exc:
                observation = f"LỖI: Tool {tool_name} thực thi thất bại: {exc}"

        print_react_step(step, thought, action_text, observation)
        trace.extend([llm_output, f"Observation: {observation}"])

    fallback = (
        f"Xin lỗi, tôi chưa thể hoàn tất tư vấn sau {MAX_ITERATIONS} bước. "
        "Vui lòng bổ sung thông tin hoặc thử lại."
    )
    print(
        f"* **Thought {MAX_ITERATIONS + 1}**: Đã đạt giới hạn tối đa "
        f"{MAX_ITERATIONS} bước, cần ngắt vòng lặp an toàn."
    )
    print(f'- **Final Answer**: *"{fallback}"*')
    return fallback


if __name__ == "__main__":
    print("==================================================")
    print("🏫 ĐẠI HỌC VINUNI - BÀI LAB 3: CHATBOT VS REACT AGENT")
    print("==================================================")
    
    # Khởi tạo Multi-Provider LLM Adapter (Đọc từ biến môi trường LLM_PROVIDER)
    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(f"🔌 LLM Provider đang hoạt động: {provider.__class__.__name__} (Model: {model_name})")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases từ config/test_cases.json\n")
    
    print("--- CHẠY CHATBOT BASELINE TRÊN TOÀN BỘ TEST CASE ---")
    for index, test_case in enumerate(tests, start=1):
        test_id = test_case.get("id", index)
        category = test_case.get("category", "Không phân loại")
        print(f"\n{'=' * 50}")
        print(f"TEST CASE {test_id}/{len(tests)} — {category}")
        run_baseline_chatbot(test_case["question"], provider)

    print("\n--- CHẠY REACT AGENT TRÊN TOÀN BỘ TEST CASE ---")
    for index, test_case in enumerate(tests, start=1):
        test_id = test_case.get("id", index)
        category = test_case.get("category", "Không phân loại")
        print(f"\n{'=' * 50}")
        print(f"TEST CASE {test_id}/{len(tests)} — {category}")
        run_react_agent(test_case["question"], provider)
