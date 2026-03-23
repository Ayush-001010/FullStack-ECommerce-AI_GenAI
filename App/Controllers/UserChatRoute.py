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
    Category : Optional[list[str]] = None
    SubCategory : Optional[list[str]] = None
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

def search_product(category : list[str] , sub_catgory : list[str] , db: Session):
    category_ids = db.query(CategoryDetails.id).filter(CategoryDetails.Name.in_(category)).all()
    category_ids = [id for (id,) in category_ids]
    products = db.query(ProductDetails).filter(ProductDetails.categoryId.in_(category_ids) , ProductDetails.SubCategory.in_(sub_catgory)).all()
    return products

def category_details(db : Session) : 
    category_details = db.query(CategoryDetails).all()
    category_names = [c.Name for c in category_details]
    return category_names

def sub_category_details(category : list[str] , db : Session) :
    
    category_ids = db.query(CategoryDetails.id).filter(CategoryDetails.Name.in_(category)).all()
    category_ids = [id for (id,) in category_ids]
    subcategories = db.query(ProductDetails.SubCategory).filter(ProductDetails.categoryId.in_(category_ids)).distinct().all()
    subcategories = [sub[0] for sub in subcategories]
    return subcategories


class OpenAIChatClass :
    role : Literal["system" , "user" , "assistant"]
    content : str


@router.post("/chat")
async def chat(chats: list[ChatRequest] , db: Session = Depends(get_db)):
    system_prompt = """
Think step by step internally, but DO NOT output reasoning. Output ONLY one JSON object.

IMPORTANT:
- In the real response to the user, you MUST output exactly ONE valid JSON object (one step only).
- The examples below show multiple turns and are NOT meant to be returned together.

You work on these steps: Start, Plan, Tool, Observe, Output.

Rules:
- Output ONLY one valid JSON object and nothing else.
- No markdown.
- JSON must be valid (double quotes for keys/strings, true/false/null only).

User Input:
- You will get array of ChatRequest objects.
- Each ChatRequest has:
  - intent: intent of user query (null at beginning)
  - missing_fields: required fields missing (null at beginning)
  - assistant_question: question assistant asks user (null at beginning)
  - userResponse: user reply (can be null)
  - AskQuestionType: "Text" or "Option" (null at beginning)
  - ToolResponse: tool output (null at beginning)
  - FinalOuptut: final message for user (null at beginning)
  - Category: list of category names (null at beginning)
  - SubCategory: list of sub category names (null at beginning)

Your Task:
- Help user find the right product.
- Initially user will give one of:
  - "Explore Products on discount now"  -> intent: "ExploreDiscountProducts"
  - "Let find the best product for you" -> intent: "BuyProduct"
- Identify intent and missing fields.
- Missing fields are: Category, SubCategory.
- Ask questions to fill missing fields (AskQuestionType must be "Text").
- Validate Category using category_details tool.
- Validate SubCategory using sub_category_details tool.
- Call search_product tool only after Category and SubCategory are known.

Output Format:
{
  "step": "Plan",
  "content": "",
  "response": [],
  "ToolName": null,
  "ToolArgs": null,
  "ToolResponse": null
}

Allowed values:
- step: "Start" | "Plan" | "Tool" | "Observe" | "Output"
- ToolName: "search_product" | "category_details" | "sub_category_details" | null
- ToolArgs is required ONLY when step is "Tool", otherwise null
- ToolResponse is used ONLY to store tool result, otherwise null

Tool Details:
- category_details: returns list of all categories
- sub_category_details: input { "category": "<string>" }, returns list of sub categories
- search_product: input { "category": "<string>", "sub_category": "<string or list of strings>" }, returns list of products

Flow:
Intent: ExploreDiscountProducts
- Ask category -> validate via category_details
- Ask sub category -> validate via sub_category_details
- Call search_product -> return products

Intent: BuyProduct
- Ask category -> validate via category_details
- Ask sub category -> validate via sub_category_details
- Call search_product -> return products

Example (multi-turn, NOT to be returned together):

{ "step": "Start", "content": "", "response": [ { "intent": null, "missing_fields": null, "assistant_question": null, "userResponse": "Let find the best product for you", "AskQuestionType": null, "Category": null, "SubCategory": null, "ToolResponse": null, "FinalOuptut": null } ], "ToolName": null, "ToolArgs": null, "ToolResponse": null }

{ "step": "Output", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["Category"], "assistant_question": "Awesome—let’s build your perfect party look. Which category are you shopping from? (Footware, Mobiles, Fashion, Electronics)", "userResponse": null, "AskQuestionType": "Text", "Category": null, "SubCategory": null, "ToolResponse": null, "FinalOuptut": null } ], "ToolName": null, "ToolArgs": null, "ToolResponse": null }

{ "step": "Start", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["Category"], "assistant_question": "Awesome—let’s build your perfect party look. Which category are you shopping from? (Footware, Mobiles, Fashion, Electronics)", "userResponse": "I’m looking for a stylish outfit for a party—something that makes me feel confident.", "AskQuestionType": "Text", "Category": null, "SubCategory": null, "ToolResponse": null, "FinalOuptut": null } ], "ToolName": null, "ToolArgs": null, "ToolResponse": null }

{ "step": "Tool", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["Category"], "assistant_question": null, "userResponse": "I’m looking for a stylish outfit for a party—something that makes me feel confident.", "AskQuestionType": "Text", "Category": ["Fashion"], "SubCategory": null, "ToolResponse": null, "FinalOuptut": null } ], "ToolName": "category_details", "ToolArgs": {}, "ToolResponse": null }

{ "step": "Observe", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["Category"], "assistant_question": null, "userResponse": "I’m looking for a stylish outfit for a party—something that makes me feel confident.", "AskQuestionType": "Text", "Category": ["Fashion"], "SubCategory": null, "ToolResponse": null, "FinalOuptut": null } ], "ToolName": "category_details", "ToolArgs": {}, "ToolResponse": ["Footware", "Mobiles", "Fashion", "Electronics"] }

{ "step": "Output", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["SubCategory"], "assistant_question": "Nice—Fashion it is. What should your outfit include? You can mention one or more: Shirt, TShirt, Jeans (example: Shirt and Jeans).", "userResponse": null, "AskQuestionType": "Text", "Category": ["Fashion"], "SubCategory": null, "ToolResponse": null, "FinalOuptut": null } ], "ToolName": null, "ToolArgs": null, "ToolResponse": null }

{ "step": "Start", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["SubCategory"], "assistant_question": "Nice—Fashion it is. What should your outfit include? You can mention one or more: Shirt, TShirt, Jeans (example: Shirt and Jeans).", "userResponse": "Shirt and Jeans", "AskQuestionType": "Text", "Category": ["Fashion"], "SubCategory": null, "ToolResponse": null, "FinalOuptut": null } ], "ToolName": null, "ToolArgs": null, "ToolResponse": null }

{ "step": "Tool", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["SubCategory"], "assistant_question": null, "userResponse": "Shirt and Jeans", "AskQuestionType": "Text", "Category": ["Fashion"], "SubCategory": ["Shirt", "Jeans"], "ToolResponse": null, "FinalOuptut": null } ], "ToolName": "sub_category_details", "ToolArgs": { "category": "Fashion" }, "ToolResponse": null }

{ "step": "Observe", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": ["SubCategory"], "assistant_question": null, "userResponse": "Shirt and Jeans", "AskQuestionType": "Text", "Category": ["Fashion"], "SubCategory": ["Shirt", "Jeans"], "ToolResponse": null, "FinalOuptut": null } ], "ToolName": "sub_category_details", "ToolArgs": { "category": "Fashion" }, "ToolResponse": ["Shirt", "TShirt", "Jeans"] }

{ "step": "Tool", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": [], "assistant_question": null, "userResponse": null, "AskQuestionType": null, "Category": ["Fashion"], "SubCategory": ["Shirt", "Jeans"], "ToolResponse": null, "FinalOuptut": null } ], "ToolName": "search_product", "ToolArgs": { "category": "Fashion", "sub_category": ["Shirt", "Jeans"] }, "ToolResponse": null }

{ "step": "Observe", "content": "", "response": [ { "intent": "BuyProduct", "missing_fields": [], "assistant_question": null, "userResponse": null, "AskQuestionType": null, "Category": ["Fashion"], "SubCategory": ["Shirt", "Jeans"], "ToolResponse": null, "FinalOuptut": null } ], "ToolName": "search_product", "ToolArgs": { "category": "Fashion", "sub_category": ["Shirt", "Jeans"] }, "ToolResponse": [ { "id": 201, "Name": "Slim Fit Party Shirt", "Price": 1222, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 15, "Rating": 4.5, "NoOfRatings": 100, "IsBestSeller": true, "Quantity": 10, "IsActive": true, "categoryId": 1, "SubCategory": "Shirt", "Description": "Something" }, { "id": 202, "Name": "Satin Black Shirt", "Price": 1799, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 20, "Rating": 4.7, "NoOfRatings": 150, "IsBestSeller": true, "Quantity": 5, "IsActive": true, "categoryId": 1, "SubCategory": "Shirt", "Description": "Something" }, { "id": 301, "Name": "Dark Wash Slim Jeans", "Price": 1999, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 10, "Rating": 4.3, "NoOfRatings": 80, "IsBestSeller": false, "Quantity": 8, "IsActive": true, "categoryId": 1, "SubCategory": "Jeans", "Description": "Something" }, { "id": 302, "Name": "Stretch Fit Black Jeans", "Price": 2299, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 12, "Rating": 4.6, "NoOfRatings": 120, "IsBestSeller": true, "Quantity": 3, "IsActive": true, "categoryId": 1, "SubCategory": "Jeans", "Description": "Something" } ] }

{ "step": "Output", "content": "Here are some great Fashion picks for your party outfit (Shirt + Jeans). Want me to filter by color (black/white/blue) or budget?", "response": [ { "intent": "BuyProduct", "missing_fields": [], "assistant_question": null, "userResponse": null, "AskQuestionType": null, "Category": ["Fashion"], "SubCategory": ["Shirt", "Jeans"], "ToolResponse": [ { "id": 201, "Name": "Slim Fit Party Shirt", "Price": 1222, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 15, "Rating": 4.5, "NoOfRatings": 100, "IsBestSeller": true, "Quantity": 10, "IsActive": true, "categoryId": 1, "SubCategory": "Shirt", "Description": "Something" }, { "id": 202, "Name": "Satin Black Shirt", "Price": 1799, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 20, "Rating": 4.7, "NoOfRatings": 150, "IsBestSeller": true, "Quantity": 5, "IsActive": true, "categoryId": 1, "SubCategory": "Shirt", "Description": "Something" }, { "id": 301, "Name": "Dark Wash Slim Jeans", "Price": 1999, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 10, "Rating": 4.3, "NoOfRatings": 80, "IsBestSeller": false, "Quantity": 8, "IsActive": true, "categoryId": 1, "SubCategory": "Jeans", "Description": "Something" }, { "id": 302, "Name": "Stretch Fit Black Jeans", "Price": 2299, "ImageKey": "Product/White_Shirt.jpg", "IsDiscounted": true, "DiscountPercentage": 12, "Rating": 4.6, "NoOfRatings": 120, "IsBestSeller": true, "Quantity": 3, "IsActive": true, "categoryId": 1, "SubCategory": "Jeans", "Description": "Something" } ], "FinalOuptut": "Here are some great Fashion picks for your party outfit (Shirt + Jeans). Want me to filter by color (black/white/blue) or budget?" } ], "ToolName": null, "ToolArgs": null, "ToolResponse": null }

"""
    openAIChats : list[OpenAIChatClass] = [
        { "role" : "system" , "content" : system_prompt }
    ]
    for chat in chats :
        openAIChats.append({ "role" : "user" , "content" : chat.json() })
    client = get_openai_client()
    print("Initial Chats ", openAIChats)
    while True:
        response = client.chat.completions.create(model = "gpt-4o",messages = openAIChats)
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
    
