// Runs exactly once while the authenticated Community Mongo volume is empty.
// The app receives readWrite on its database, never root or dbOwner.
(function () {
  const user = process.env.MONGO_APP_USER;
  const password = process.env.MONGO_APP_PASSWORD;
  const dbName = process.env.MONGO_INITDB_DATABASE || 'tinymrp';

  if (!user || !password) {
    throw new Error('MONGO_APP_USER and MONGO_APP_PASSWORD are required');
  }

  const appDb = db.getSiblingDB(dbName);
  if (!appDb.getUser(user)) {
    appDb.createUser({
      user: user,
      pwd: password,
      roles: [{ role: 'readWrite', db: dbName }],
    });
  }
})();
