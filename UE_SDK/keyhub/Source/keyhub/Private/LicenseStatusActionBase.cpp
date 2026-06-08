// Fill out your copyright notice in the Description page of Project Settings.


#include "LicenseStatusActionBase.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Json.h"
#include "JsonUtilities.h"

ULicenseStatusActionBase* ULicenseStatusActionBase::LicenseStatusAsync(const UObject* WorldContextObject, const FString& Key, const FString& ProjectName, const FString URL)
{
    ULicenseStatusActionBase* Node = NewObject<ULicenseStatusActionBase>();
    Node->KeyInternal = Key;
    Node->ProjectNameInternal = ProjectName;
    Node->CurrentURL = URL;
    return Node;
}

void ULicenseStatusActionBase::Activate()
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(CurrentURL);
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));

    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);
    
    JsonObject->SetStringField(TEXT("project_name"), ProjectNameInternal);
    JsonObject->SetStringField(TEXT("machine_code"), KeyInternal);

    FString Payload;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
    Request->SetContentAsString(Payload);

    // Bind non-blocking callback
    Request->OnProcessRequestComplete().BindUObject(this, &ULicenseStatusActionBase::OnResponseReceived);
    Request->ProcessRequest();
}

void ULicenseStatusActionBase::OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful)
{
    bool bValid = false;
    FString Message = TEXT("Network error or no response");

    if (bWasSuccessful && Response.IsValid())
    {
        bValid = true;
        
        OnSuccess.Broadcast(true, Response->GetContentAsString());
    }
    else
    {
        OnFailure.Broadcast(false,TEXT("Error"));
    }

}
