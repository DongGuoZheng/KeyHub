#pragma once

#include "Kismet/BlueprintAsyncActionBase.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "KeyHubRegisterAsync.generated.h"

/** Result delegate: fires with success flag and a message string */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FKeyHubRegisterDelegate, bool, bSuccess, const FString&, Message);

UCLASS()
class KEYHUB_API UKeyHubRegisterAsync : public UBlueprintAsyncActionBase
{
    GENERATED_BODY()
public:
    /**
     * Async register a key against the KeyHub service.
     * Connects to OnSuccess or OnFailure when complete — does NOT block the game thread.
     * @param Key          The license key to register (e.g. "KH-A1B2C3D4-E5F6G7H8")
     * @param ProjectName  The project name (must match exactly)
     * @param Remarks      Optional remarks / description
     */
    UFUNCTION(BlueprintCallable,
              meta = (DisplayName = "Register Project (Async)",
                      BlueprintInternalUseOnly = "true",
                      WorldContext = "WorldContextObject"),
              Category = "KeyHub|Auth")
    static UKeyHubRegisterAsync* RegisterProjectAsync(const UObject* WorldContextObject,
                                                      const FString& Key,
                                                      const FString& ProjectName,
                                                      const FString& Remarks);

    /** Fires when the server returns success=true */
    UPROPERTY(BlueprintAssignable)
    FKeyHubRegisterDelegate OnSuccess;

    /** Fires when the server returns success=false, or a network/parse error occurs */
    UPROPERTY(BlueprintAssignable)
    FKeyHubRegisterDelegate OnFailure;

    virtual void Activate() override;

private:
    void OnResponseReceived(FHttpRequestPtr Request, FHttpResponsePtr Response, bool bWasSuccessful);

    FString KeyInternal;
    FString ProjectNameInternal;
    FString RemarksInternal;
};
