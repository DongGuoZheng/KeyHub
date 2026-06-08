#include "KeyHubAuthAsync.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"

UKeyHubAuthAsync* UKeyHubAuthAsync::VerifyProjectAsync(const UObject* WorldContextObject,
                                                      const FString& Key,
                                                      const FString& ProjectName)
{
    UKeyHubAuthAsync* Node = NewObject<UKeyHubAuthAsync>();
    Node->KeyInternal = Key;
    Node->ProjectNameInternal = ProjectName;
    return Node;
}

void UKeyHubAuthAsync::Activate()
{
    // Build POST request to https://keyhub.zg.gg/api/verify
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(TEXT("https://keyhub.zg.gg/api/verify"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

    // Payload: { "key": "...", "project_name": "..." }
    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);
    JsonObject->SetStringField(TEXT("key"), KeyInternal);
    JsonObject->SetStringField(TEXT("project_name"), ProjectNameInternal);

    FString Payload;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
    Request->SetContentAsString(Payload);

    // Bind non-blocking callback
    Request->OnProcessRequestComplete().BindUObject(this, &UKeyHubAuthAsync::OnResponseReceived);
    Request->ProcessRequest();
}

void UKeyHubAuthAsync::OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{
    bool bValid = false;
    FString Message = TEXT("Network error or no response");

    if (bWasSuccessful && Response.IsValid())
    {
        TSharedPtr<FJsonObject> RespObj;
        TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
        if (FJsonSerializer::Deserialize(Reader, RespObj) && RespObj.IsValid())
        {
            // Read "valid" field (bool)
            if (RespObj->HasField(TEXT("valid")))
                bValid = RespObj->GetBoolField(TEXT("valid"));

            // Read "message" field (string)
            if (RespObj->HasField(TEXT("message")))
                Message = RespObj->GetStringField(TEXT("message"));
        }
        else
        {
            Message = FString::Printf(TEXT("JSON parse error (HTTP %d)"), Response->GetResponseCode());
        }
    }

    if (bValid)
        OnSuccess.Broadcast(true, Message);
    else
        OnFailure.Broadcast(false, Message);
}
