#pragma once

#include "Kismet/BlueprintAsyncActionBase.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "KeyHubAuthAsync.generated.h"

/** Result delegate: fires with valid=true/false and a message string */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FKeyHubVerifyDelegate, bool, bValid, const FString&, Message);

UCLASS()
class KEYHUB_API UKeyHubAuthAsync : public UBlueprintAsyncActionBase
{
    GENERATED_BODY()
public:
    /**
     * Async verify a key + project_name against the KeyHub service.
     * Connects to OnSuccess or OnFailure when complete — does NOT block the game thread.
     * @param Key          The license key to verify (e.g. "KH-A1B2C3D4-E5F6G7H8")
     * @param ProjectName  The project name to verify against (must match exactly)
     */
    UFUNCTION(BlueprintCallable,
              meta = (DisplayName = "Verify Project (Async)",
                      BlueprintInternalUseOnly = "true",
                      WorldContext = "WorldContextObject"),
              Category = "KeyHub|Auth")
    static UKeyHubAuthAsync* VerifyProjectAsync(const UObject* WorldContextObject,
                                                const FString& Key,
                                                const FString& ProjectName);

    /** Fires when the server returns valid=true */
    UPROPERTY(BlueprintAssignable)
    FKeyHubVerifyDelegate OnSuccess;

    /** Fires when the server returns valid=false, or a network/parse error occurs */
    UPROPERTY(BlueprintAssignable)
    FKeyHubVerifyDelegate OnFailure;

    virtual void Activate() override;

private:
    void OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);

    FString KeyInternal;
    FString ProjectNameInternal;
};
