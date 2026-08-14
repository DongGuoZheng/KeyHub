// Fill out your copyright notice in the Description page of Project Settings.


#include "PlayHeartbeatActionBase.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"

UPlayHeartbeatActionBase* UPlayHeartbeatActionBase::PlayHeartbeatAsync(const UObject* WorldContextObject, const FString SessionID, const FString URL)
{
    UPlayHeartbeatActionBase* Node = NewObject<UPlayHeartbeatActionBase>();
    Node->CurrentSessionID = SessionID;
    Node->CurrentURL = URL;
    return Node;
}

void UPlayHeartbeatActionBase::Activate()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(CurrentURL);
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);

    JsonObject->SetStringField(TEXT("session_id"), CurrentSessionID);

    FString Payload;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
    Request->SetContentAsString(Payload);

    // Bind non-blocking callback
    Request->OnProcessRequestComplete().BindUObject(this, &UPlayHeartbeatActionBase::OnResponseReceived);
    Request->ProcessRequest();
}

void UPlayHeartbeatActionBase::OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{


    if (bWasSuccessful && Response.IsValid())
    {

        OnSuccess.Broadcast(true, Response->GetContentAsString());
    }
    else
    {
        OnFailure.Broadcast(false, TEXT("Error"));
    }

}
