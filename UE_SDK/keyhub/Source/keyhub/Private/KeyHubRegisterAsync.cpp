#include "KeyHubRegisterAsync.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"

UKeyHubRegisterAsync* UKeyHubRegisterAsync::RegisterProjectAsync(const UObject* WorldContextObject,
                                                                  const FString& Key,
                                                                  const FString& ProjectName,
                                                                  const FString& Remarks)
{
    UKeyHubRegisterAsync* Node = NewObject<UKeyHubRegisterAsync>();
    Node->KeyInternal = Key;
    Node->ProjectNameInternal = ProjectName;
    Node->RemarksInternal = Remarks;
    return Node;
}

void UKeyHubRegisterAsync::Activate()
{
    // Build POST request to https://keyhub.zg.gg/api/register
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(TEXT("https://keyhub.zg.gg/api/register"));
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

    // Payload: { "key": "...", "project_name": "...", "remarks": "..." }
    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);
    JsonObject->SetStringField(TEXT("key"), KeyInternal);
    JsonObject->SetStringField(TEXT("project_name"), ProjectNameInternal);
    JsonObject->SetStringField(TEXT("remarks"), RemarksInternal);

    FString Payload;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
    Request->SetContentAsString(Payload);

    // Bind non-blocking callback
    Request->OnProcessRequestComplete().BindUObject(this, &UKeyHubRegisterAsync::OnResponseReceived);
    Request->ProcessRequest();
}

void UKeyHubRegisterAsync::OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{
    bool bSuccess = false;
    FString Message = TEXT("Network error or no response");

    if (bWasSuccessful && Response.IsValid())
    {
        TSharedPtr<FJsonObject> RespObj;
        TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Response->GetContentAsString());
        if (FJsonSerializer::Deserialize(Reader, RespObj) && RespObj.IsValid())
        {
            // Read "success" field (bool)
            if (RespObj->HasField(TEXT("success")))
                bSuccess = RespObj->GetBoolField(TEXT("success"));

            // Read "message" field (string)
            if (RespObj->HasField(TEXT("message")))
                Message = RespObj->GetStringField(TEXT("message"));
        }
        else
        {
            Message = FString::Printf(TEXT("JSON parse error (HTTP %d)"), Response->GetResponseCode());
        }
    }

    if (bSuccess)
        OnSuccess.Broadcast(true, Message);
    else
        OnFailure.Broadcast(false, Message);
}
