// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintAsyncActionBase.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "PlayStartActionBase.generated.h"

/**
 * 
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FKeyHubPlayStartDelegate, bool, bValid, const FString&, Message);
UCLASS()
class KEYHUB_API UPlayStartActionBase : public UBlueprintAsyncActionBase
{
	GENERATED_BODY()

    UFUNCTION(BlueprintCallable,
        meta = (DisplayName = "PlayStart (Async)",
            BlueprintInternalUseOnly = "true",
            WorldContext = "WorldContextObject"),
        Category = "KeyHub|Auth")
    static UPlayStartActionBase* PlayStartAsync(const UObject* WorldContextObject,
        const FString& Key,
        const FString& ProjectName,
        const FString URL = TEXT("https://keyhub.zg.gg/api/play/start"));

    /** Fires when the server returns valid=true */
    UPROPERTY(BlueprintAssignable)
    FKeyHubPlayStartDelegate OnSuccess;

    /** Fires when the server returns valid=false, or a network/parse error occurs */
    UPROPERTY(BlueprintAssignable)
    FKeyHubPlayStartDelegate OnFailure;

    virtual void Activate() override;

private:
    void OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);

    FString KeyInternal;
    FString ProjectNameInternal;
    FString CurrentURL;
	
};
