-- Normalize past-tense outcome strings to canonical WIN/LOSS/PUSH/VOID
UPDATE picks SET outcome = 'WIN'  WHERE outcome IN ('WON', 'W', 'HIT', 'TRUE', 'YES', '1');
UPDATE picks SET outcome = 'LOSS' WHERE outcome IN ('LOST', 'L', 'MISS', 'FALSE', 'NO', '0');
UPDATE picks SET outcome = 'PUSH' WHERE outcome IN ('PUSHED', 'TIE');
UPDATE picks SET outcome = 'VOID' WHERE outcome IN ('VOIDED', 'CANCELLED');
