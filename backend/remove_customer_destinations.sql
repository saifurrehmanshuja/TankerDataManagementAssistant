-- Remove placeholder "Customer X", "Customer Y", etc. destinations from the database
-- This script removes all destinations with names starting with "Customer"

-- First, update any tankers that reference these destinations to NULL
-- (or you can reassign them to a valid destination if needed)
UPDATE tankers 
SET destination_id = NULL 
WHERE destination_id IN (
    SELECT destination_id 
    FROM destinations 
    WHERE destination_name LIKE 'Customer%'
);

-- Update tanker_history records
UPDATE tanker_history 
SET destination_id = NULL 
WHERE destination_id IN (
    SELECT destination_id 
    FROM destinations 
    WHERE destination_name LIKE 'Customer%'
);

-- Delete the placeholder destinations
DELETE FROM destinations 
WHERE destination_name LIKE 'Customer%';

-- Verify removal (optional - uncomment to check)
-- SELECT * FROM destinations ORDER BY destination_name;

