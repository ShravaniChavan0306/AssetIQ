
from chatbot.mysql_chatbot import answer_question


print("=" * 55)
print("             ASSETIQ MYSQL CHATBOT")
print("=" * 55)

while True:
    question = input("\nYou: ").strip()

    if question.lower() in ("exit", "quit", "bye"):
        print("AssetIQ: Goodbye!")
        break

    answer = answer_question(question)

    print("\nAssetIQ:")
    print(answer)
