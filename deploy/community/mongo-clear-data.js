// Exact-restore preparation for the TinyMRP application database.
//
// `mongorestore --drop` only drops collections that are present in its
// archive. A collection created after a backup would otherwise survive the
// restore and leave the database in a state that never existed at backup time.
// Drop every non-system collection first, while preserving database-scoped
// authentication metadata. The lifecycle scripts run this only after archive
// integrity/content verification and after stopping the app.
(function () {
  const dbName = process.env.MONGO_INITDB_DATABASE;
  if (!dbName) {
    throw new Error('MONGO_INITDB_DATABASE is required');
  }

  const target = db.getSiblingDB(dbName);
  const collections = target.getCollectionInfos({}, { nameOnly: true });
  let dropped = 0;

  collections.forEach((info) => {
    if (info.name.startsWith('system.')) {
      return;
    }
    if (!target.getCollection(info.name).drop()) {
      throw new Error('failed to drop collection: ' + info.name);
    }
    dropped += 1;
  });

  print('[tinymrp] cleared ' + dropped + ' application collection(s) from ' + dbName);
})();
