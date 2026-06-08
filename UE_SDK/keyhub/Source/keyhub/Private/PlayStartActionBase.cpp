// Fill out your copyright notice in the Description page of Project Settings.


#include "PlayStartActionBase.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"

UPlayStartActionBase* UPlayStartActionBase::PlayStartAsync(const UObject* WorldContextObject, const FString& Key, const FString& ProjectName, const FString URL)
{
    UPlayStartActionBase* Node = NewObject<UPlayStartActionBase>();
    Node->KeyInternal = Key;
    Node->ProjectNameInternal = ProjectName;
    Node->CurrentURL = URL;
    return Node;
}

void UPlayStartActionBase::Activate()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(CurrentURL);
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);

    JsonObject->SetStringField(TEXT("project_name"), ProjectNameInternal);
    JsonObject->SetStringField(TEXT("machine_code"), KeyInternal);
    JsonObject->SetStringField(TEXT("client_version"), TEXT("1.0.0"));

    FString Payload;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
    Request->SetContentAsString(Payload);

    // Bind non-blocking callback
    Request->OnProcessRequestComplete().BindUObject(this, &UPlayStartActionBase::OnResponseReceived);
    Request->ProcessRequest();
}

void UPlayStartActionBase::OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
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

