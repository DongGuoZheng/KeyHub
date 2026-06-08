// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintAsyncActionBase.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "PlayEndActionBase.generated.h"

/**
 * 
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FKeyHubPlayEndDelegate, bool, bValid, const FString&, Message);

UCLASS()
class KEYHUB_API UPlayEndActionBase : public UBlueprintAsyncActionBase
{
	GENERATED_BODY()
    UFUNCTION(BlueprintCallable,
        meta = (DisplayName = "PlayEnd (Async)",
            BlueprintInternalUseOnly = "true",
            WorldContext = "WorldContextObject"),
        Category = "KeyHub|Auth")
    static UPlayEndActionBase* PlayEndAsync(const UObject* WorldContextObject,
        const FString SessionID,
        const FString URL = TEXT("https://keyhub.zg.gg/api/play/end"));

    /** Fires when the server returns valid=true */
    UPROPERTY(BlueprintAssignable)
    FKeyHubPlayEndDelegate OnSuccess;

    /** Fires when the server returns valid=false, or a network/parse error occurs */
    UPROPERTY(BlueprintAssignable)
    FKeyHubPlayEndDelegate OnFailure;

    virtual void Activate() override;

private:
    void OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);

    FString CurrentSessionID;
    FString CurrentURL;
	
};
