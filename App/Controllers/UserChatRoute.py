from fastapi import APIRouter  , Depends
from pydantic import BaseModel
from typing import Any , Optional
from Model.Category import CategoryDetails
from Model.Product import ProductDetails
from sqlalchemy.orm import Session
from OpenAIClient import get_openai_client
from Database import SessionLocal
import json
from typing import Literal


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# intent
# filters (normalized)
# missing_fields
# assistant_question (if missing_fields not empty)
# products (if you have enough info and queried DB)
# assistant_message (final text to display)

class ChatRequest (BaseModel):
    intent: Optional[str]= None
    missing_fields: Optional[list[str]] = None
    assistant_question: Optional[str] = None
    userResponse: Optional[str] = None
    AskQuestionType: Optional[str] = None # "Text"
    Category : Optional[str] = None
    SubCategory : Optional[str] = None
    ToolResponse : Optional[Any] = None
    FinalOuptut : Optional[Any] = None


def product_to_dict(p: ProductDetails) -> dict:
    return {
        "id": p.id,
        "Name": p.Name,
        "Description": p.Description,
        "Price": float(p.Price) if p.Price is not None else None,
        "ImageKey": p.ImageKey,
        "IsDiscounted": p.IsDiscounted,
        "DiscountPercentage": p.DiscountPercentage,
        "Rating": float(p.Rating) if p.Rating is not None else None,
        "NoOfRatings": p.NoOfRatings,
        "IsBestSeller": p.IsBestSeller,
        "Quantity": p.Quantity,
        "IsActive": p.IsActive,
        "categoryId": p.categoryId,
        "SubCategory": p.SubCategory,
    }

def search_product(category : str , sub_catgory : str , db: Session):
    categoryID = db.query(CategoryDetails).filter(CategoryDetails.Name == category).first().id
    products = db.query(ProductDetails).filter(ProductDetails.categoryId == categoryID , ProductDetails.SubCategory == sub_catgory).all()
    return products

def category_details(db : Session) : 
    category_details = db.query(CategoryDetails).all()
    category_names = [c.Name for c in category_details]
    return category_names

def sub_category_details(category : str , db : Session) :
    print("")
    print("Category in sub_category_details is ", category)
    categoryID = db.query(CategoryDetails).filter(CategoryDetails.Name == category).first().id
    sub_category_details = db.query(ProductDetails.SubCategory).filter(ProductDetails.categoryId == categoryID).distinct().all()
    subcategories = [row[0] for row in sub_category_details] 
    print(subcategories)
    return subcategories


class OpenAIChatClass :
    role : Literal["system" , "user" , "assistant"]
    content : str


@router.post("/chat")
async def chat(chats: list[ChatRequest] , db: Session = Depends(get_db)):
    system_prompt = """
    Think step by step internally, but DO NOT output reasoning. Output ONLY the JSON object.
    You work on Start, Plan and Output Steps.
    Alway solve one step at a time and give output in below Output Formate.


    Rule:
        - Output ONLY one valid JSON object and nothing else.
        - No markdown.
        - Think step by step internally, but DO NOT output reasoning.
        
    User Input :
        - You will get array of ChatRequest objects.
        - Each ChatRequest have 
            - intent : which is the intent of user query. It must be None at the beginning.
            - missing_fields : which is required fields that are missing to resolve user query. It must be None at the beginning.
            - assistant_question : which is the question that assistant need to ask user to get missing information. It must be None at the beginning.
            - userResponse : which is the response of user to assistant question. It some time can be None at the beginning.
            - AskQuestionType : which is the type of question that assistant need to ask user. It can be "Text" or "Option". It must be None at the beginning.
            - Category : which is the category of product user want to buy. It must be None at the beginning.
            - SubCategory : which is the sub category of product user want to buy. It must be None at the beginning.
            - ToolResponse : which is the response of tool that assistant used to resolve user query. It must be None at the beginning.
            - FinalOuptut : which is the final output that assistant will give to user after resolving user query. It must be None at the beginning.

    Your Task :
        - Your task is to help user to find the right product which user wants to buy.
        - Initially user will give any one of response to you:
            - "Explore Products on discount now"
            - "I want to buy a new phone"
        - Based on user query you need to find intent of user query and create new ChatRequest object and fill intent.
            - "Explore Products on discount now" : intent will be "ExploreDiscountProducts"
            - "I want to buy a new phone" : intent will be "BuyProduct"
        - After finding intent you alway need to know about missing fields.
        - Missing fields are:
            - Category : which is the category of product user want to buy. 
            - SubCategory : which is the sub category of product user want to buy.
        - After finding missing fields. Set value Category and SubCategory in ChatRequest object.
        -After find missing fields you need to ask user question and get response from user.
            - you need set value AskQuestionType to "Text" . so that user can give response in text format.
        - After finding that you have call search_product tool/fuction which return list of products based on category and subcategory. Return to user.

    Output Formate -
        {
            "step": "Plan",
            "content": "",
            "response": [],
            "ToolName": null,
            "ToolArgs": null,
            "ToolResponse": null
        }
        Allowed values:
            - "step" must be exactly one of: "Start", "Plan", "Tool", "Observe", "Output" .
            - "ToolName" must be one of: "search_product", "category_details", "sub_category_details", or null
            - "ToolArgs" is required when step is "Tool", otherwise null
            - "ToolResponse" is used only to store the tool result, otherwise null
        - Always give output in above format. Don't give output in any other format. Always follow above format strictly. Always give output as plain text. Don't use any markdown formatting. Don't use any code formatting. Just give output as plain text.
        - In the senior steps like Plan or Observe the output still follow above format but ToolName and ToolResponse will be null. In the Tool step ToolName and ToolResponse will have value based on tool you used. In the Output step response will have value and other fields will be null.
   
   Tool Details: 
        - search_product : which take category and subcategory as input and return list of products based on category and subcategory. You can call this function only once you have both category and subcategory.
        - category_details : which return list of all categories and their details. You can call this function any time to get details of all categories. You can use this function to give user option of category.
        - sub_category_details : which take category as input and return list of all sub categories of that category. You can call this function any time to get details of all sub categories of a category. You can use this function to give user option of sub category.

    Flow - 
        Intent :
            - ExploreDiscountProducts :
                - Ask user about category of product. (missing field will be category)
                - After getting category from user verify category with database using category_details tool. If category is not present in database then ask user to choose category from given options. (missing field will be category)
                - After getting correct category from user. Set category in ChatRequest.
                - Ask user about sub category of product. (missing field will be sub category)
                - After getting sub category from user verify sub category with database using sub_category_details tool.
                - After getting correct sub category from user. Set sub category in ChatRequest.
                - Call search_product tool to get list of products based on category and sub category.
                - Return products to user.

    Example (valid JSON)
User input chats
{
  "step": "Start",
  "content": "",
  "response": [
    {
      "intent": null,
      "missing_fields": null,
      "assistant_question": null,
      "userResponse": "I want shoes",
      "AskQuestionType": null,
      "Category": null,
      "SubCategory": null,
      "ToolResponse": null,
      "FinalOuptut": null
    }
  ],
  "ToolName": null,
  "ToolArgs": null,
  "ToolResponse": null
}

Assistant tool call category_details (validate inferred category)
{
  "step": "Tool",
  "content": "",
  "response": [
    {
      "intent": "BuyProduct",
      "missing_fields": [],
      "assistant_question": null,
      "userResponse": "I want shoes",
      "AskQuestionType": null,
      "Category": "Footware",
      "SubCategory": "Shoes",
      "ToolResponse": null,
      "FinalOuptut": null
    }
  ],
  "ToolName": "category_details",
  "ToolArgs": {},
  "ToolResponse": null
}

Backend ToolResult after running category_details
{
  "step": "ToolResult",
  "content": "",
  "response": [
    {
      "intent": "BuyProduct",
      "missing_fields": [],
      "assistant_question": null,
      "userResponse": "I want shoes",
      "AskQuestionType": null,
      "Category": "Footware",
      "SubCategory": "Shoes",
      "ToolResponse": null,
      "FinalOuptut": null
    }
  ],
  "ToolName": "category_details",
  "ToolArgs": {},
  "ToolResponse": ["Footware", "Mobiles", "Clothing"]
}

Assistant tool call sub_category_details (validate inferred subcategory)
{
  "step": "Tool",
  "content": "",
  "response": [
    {
      "intent": "BuyProduct",
      "missing_fields": [],
      "assistant_question": null,
      "userResponse": "I want shoes",
      "AskQuestionType": null,
      "Category": "Footware",
      "SubCategory": "Shoes",
      "ToolResponse": null,
      "FinalOuptut": null
    }
  ],
  "ToolName": "sub_category_details",
  "ToolArgs": { "category": "Footware" },
  "ToolResponse": null
}

Backend ToolResult after running sub_category_details
{
  "step": "ToolResult",
  "content": "",
  "response": [
    {
      "intent": "BuyProduct",
      "missing_fields": [],
      "assistant_question": null,
      "userResponse": "I want shoes",
      "AskQuestionType": null,
      "Category": "Footware",
      "SubCategory": "Shoes",
      "ToolResponse": null,
      "FinalOuptut": null
    }
  ],
  "ToolName": "sub_category_details",
  "ToolArgs": { "category": "Footware" },
  "ToolResponse": ["Shoes", "Sandals", "Formal Shoes"]
}

Assistant tool call search_product
{
  "step": "Tool",
  "content": "",
  "response": [
    {
      "intent": "BuyProduct",
      "missing_fields": [],
      "assistant_question": null,
      "userResponse": null,
      "AskQuestionType": null,
      "Category": "Footware",
      "SubCategory": "Shoes",
      "ToolResponse": null,
      "FinalOuptut": null
    }
  ],
  "ToolName": "search_product",
  "ToolArgs": { "category": "Footware", "sub_category": "Shoes" },
  "ToolResponse": null
}

Backend ToolResult after running search_product
{
  "step": "ToolResult",
  "content": "",
  "response": [
    {
      "intent": "BuyProduct",
      "missing_fields": [],
      "assistant_question": null,
      "userResponse": null,
      "AskQuestionType": null,
      "Category": "Footware",
      "SubCategory": "Shoes",
      "ToolResponse": null,
      "FinalOuptut": null
    }
  ],
  "ToolName": "search_product",
  "ToolArgs": { "category": "Footware", "sub_category": "Shoes" },
  "ToolResponse": [
    { "id": 1, "name": "Nike Air Max", "price": 100, "discount": 10 },
    { "id": 2, "name": "Adidas Superstar", "price": 80, "discount": 20 }
  ]
}

Assistant final output
{
  "step": "Output",
  "content": "Here are shoes in Footware category",
  "response": [
    {
      "intent": "BuyProduct",
      "missing_fields": [],
      "assistant_question": null,
      "userResponse": null,
      "AskQuestionType": null,
      "Category": "Footware",
      "SubCategory": "Shoes",
      "ToolResponse": [
        { "id": 1, "name": "Nike Air Max", "price": 100, "discount": 10 },
        { "id": 2, "name": "Adidas Superstar", "price": 80, "discount": 20 }
      ],
      "FinalOuptut": "Here are shoes in Footware category"
    }
  ],
  "ToolName": null,
  "ToolArgs": null,
  "ToolResponse": null
}

"""
    
    openAIChats : list[OpenAIChatClass] = [
        { "role" : "system" , "content" : system_prompt }
    ]
    for chat in chats :
        openAIChats.append({ "role" : "user" , "content" : chat.json() })
    client = get_openai_client()
    print("Initial Chats ", openAIChats)
    while True:
        response = client.chat.completions.create(model = "gpt-4o-mini",messages = openAIChats)
        assistant_text = response.choices[0].message.content
        print("Assistant text:", repr(assistant_text))
        print("")
        print("Starting.... ", assistant_text)
        print("")
        result = json.loads(assistant_text)

        openAIChats.append({"role": "assistant", "content": assistant_text})

        
        if result.get("step") == "Output":

            return {
                "data": {
                    "response": result.get("response"),
                },
                "success": True,
            }

        elif result.get("step") == "Plan":
            print("Response 🤖 ", assistant_text)
        elif result.get("step") == "Tool":
            tool_name = result.get("ToolName")
            if tool_name == "search_product":
                arr = result.get("response")
                category = arr[-1].get("Category")
                sub_category = arr[-1].get("SubCategory")
                tool_response = search_product(category, sub_category, db)
                tool_response_json = [product_to_dict(p) for p in tool_response]
                arr.append({
                    "intent" : arr[-1].get("intent") ,
                    "missing_fields" : arr[-1].get("missing_fields") ,
                    "assistant_question" : arr[-1].get("assistant_question") ,
                    "userResponse" : arr[-1].get("userResponse") ,
                    "AskQuestionType" : arr[-1].get("AskQuestionType") ,
                    "Category" : category ,
                    "SubCategory" : sub_category,
                    "ToolResponse" : tool_response_json
                })
                openAIChats.append({"role": "assistant", "content": json.dumps(arr)})
            elif tool_name == "category_details":
                arr = result.get("response")
                tool_response = category_details(db)
                arr.append({
                    "intent" : arr[-1].get("intent") ,
                    "missing_fields" : arr[-1].get("missing_fields") ,
                    "assistant_question" : arr[-1].get("assistant_question") ,  
                    "userResponse" : arr[-1].get("userResponse") ,
                    "AskQuestionType" : arr[-1].get("AskQuestionType") ,
                    "Category" : arr[-1].get("Category") ,
                    "SubCategory" : arr[-1].get("SubCategory") ,
                    "ToolResponse" : tool_response
                })
                openAIChats.append({"role": "assistant", "content": json.dumps(arr)})
            elif tool_name == "sub_category_details":
                arr = result.get("response")
                print("Arr is ", arr)
                print("")
    
                category = None
                category = arr[-1].get("Category")
                print("Category is ", category)
                print("")
                tool_response = sub_category_details(category, db)
                arr.append({
                    "intent" : arr[-1].get("intent") ,
                    "missing_fields" : arr[-1].get("missing_fields") ,
                    "assistant_question" : arr[-1].get("assistant_question") ,  
                    "userResponse" : arr[-1].get("userResponse") ,
                    "AskQuestionType" : arr[-1].get("AskQuestionType") ,
                    "Category" : category ,
                    "SubCategory" : arr[-1].get("SubCategory") ,
                    "ToolResponse" : json.dumps(tool_response)
                })
                openAIChats.append({"role": "assistant", "content": json.dumps(arr)})
            
        else:
            print("Starting.... ", assistant_text)
    
