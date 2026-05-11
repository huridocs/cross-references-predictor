The "Modified" ID Snapshot Strategy
1. Identifying Deletions (The Core of Option 2)

This remains your most reliable path.

    Action: Before the extraction job, your service requests only the _id field for all documents in this collection.

    Sync Logic:
    Python

    # Pseudo-code for your sync service
    current_ids = set(uwazi_api.get_all_reference_ids()) 
    cached_ids = set(local_db.get_all_ids())

    # Find IDs in cache but NOT in Uwazi
    deleted_ids = cached_ids - current_ids
    local_db.bulk_delete(deleted_ids)

2. Identifying New References (Using the _id)

Even without a createdAt field, you can use the ObjectId to find new records.

    The Trick: Since ObjectIds are chronological, you can query for documents where the _id is "greater than" the last _id you successfully synced.

    Query Logic:
    db.connections.find({ _id: { $gt: ObjectId("LAST_SYNCED_ID_HERE") } })

    Benefit: This avoids a full collection scan and only pulls the newest entries.

3. Handling Updates (The Tricky Part)

In Uwazi, "References" are rarely edited in place. Usually, a user deletes a reference and creates a new one, or changes the metadata of the Entity it points to.

    If a user moves a highlight (Selection Rectangles): If Uwazi's UI updates the existing document without changing the _id, you won't see it via the $gt ID query.

    The Workaround: Check the __v field (Version Key) in your sample data.

        Mongoose increments __v whenever a document is significantly updated.

        Action: When you do your ID Snapshot (Step 1), also pull the __v field. If local_v < remote_v, re-fetch that specific document.

Optimized Sync Workflow

To keep your service fast, perform the sync in this order:

    Fast Add: Fetch everything where _id > last_max_id. Add these to your predictive model.

    ID Sweep: Fetch a list of all _id and __v.

        Compare the list to find Deletions (missing IDs).

        Compare Version Keys to find Updates.

    Clean up: Remove the deleted entries from your vector index/cache.

A Note on Uwazi Performance

If your Uwazi instance has tens of thousands of references, fetching all IDs as a flat list can still be heavy. If you hit performance issues, you can optimize the ID Sweep by chunking the request by hub or file ID, especially if the extraction service is only evaluating one specific PDF at a time.

    Observation: In your data, notice the hub field. In Uwazi, references are grouped by "hubs" (connecting two or more points). If you are evaluating a specific PDF, you could theoretically just sync the references related to the file ID in your JSON, which would be much faster than a global sync.