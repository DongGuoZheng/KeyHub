// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintAsyncActionBase.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "PlayHeartbeatActionBase.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FKeyHubPlayHeartbeatDelegate, bool, bValid, const FString&, Message);

UCLASS()
class KEYHUB_API UPlayHeartbeatActionBase : public UBlueprintAsyncActionBase
{
	GENERATED_BODY()

    UFUNCTION(BlueprintCallable,
        meta = (DisplayName = "PlayHeartbeat (Async)",
            BlueprintInternalUseOnly = "true",
            WorldContext = "WorldContextObject"),
        Category = "KeyHub|Auth")
    static UPlayHeartbeatActionBase* PlayHeartbeatAsync(const UObject* WorldContextObject,
        const FString SessionID,
        const FString URL = TEXT("https://keyhub.zg.gg/api/play/heartbeat"));

    /** Fires when the server returns valid=true */
    UPROPERTY(BlueprintAssignable)
    FKeyHubPlayHeartbeatDelegate OnSuccess;

    /** Fires when the server returns valid=false, or a network/parse error occurs */
    UPROPERTY(BlueprintAssignable)
    FKeyHubPlayHeartbeatDelegate OnFailure;

    virtual void Activate() override;

private:
    void OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);

    FString CurrentSessionID;
    FString CurrentURL;
};
