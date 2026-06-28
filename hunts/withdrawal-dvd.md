# HUNT: DVD Withdrawal Challenge

## Target
- Program: Damn Vulnerable DeFi v4 (local benchmark)
- Contract: L1Gateway, L1Forwarder, TokenBridge
- Chain: local Foundry
- Impact: bridge drain via suspicious L2 withdrawal (999k DVT of 1M)

## Claim
I think finalizing a suspicious withdrawal in L1Gateway marks the leaf processed even when L1Forwarder reverts on duplicate forwardMessage, letting an operator block the drain while satisfying all finalize checks.

## Code Path
- Entry: L1Gateway.finalizeWithdrawal
- State: finalizedWithdrawals[leaf]=true before external call
- External: assembly call -> L1Forwarder.forwardMessage -> TokenBridge.executeTokenWithdrawal
- Block: successfulMessages[messageId] already true -> AlreadyForwarded revert; call returns success=false, leaf stays finalized

## Hypothesis
Pre-mark successfulMessages for nonce-2 inner message id. Gateway finalizes all 4 leaves; suspicious forward reverts; only 3 small (10 DVT) withdrawals execute. Bridge keeps >99%.

## Falsifiers
- Wrong messageId (outer calldata vs inner bytes) -> suspicious withdrawal still executes
- Gateway reverts if forward fails -> theory wrong (it does not revert)

## Evidence
- Failing assert: bridge 970e18 vs min 990000e18 (suspicious 999000e18 executed)
- Correct messageId: 0xfba34302c358f2edddfeb2fd67dc37cfa079d85bd83797e0b4103a6965a314f5
- forwardMessage l2Sender arg is receiver (0xea47...), not l2Handler
- successfulMessages mapping slot is 1 (ReentrancyGuard._status occupies slot 0)

## Decision
- Status: keep — confirmed, fixed in test_withdrawal
- Fix pattern: compute messageId from forwardMessage args (inner message bytes), not full gateway calldata
