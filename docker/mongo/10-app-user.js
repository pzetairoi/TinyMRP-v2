// Least-privilege application user (OPS-DBAUTH-01).
//
// Mongo runs everything in /docker-entrypoint-initdb.d ONCE, on the first boot
// of an empty data directory, already authenticated as the root user created
// from MONGO_INITDB_ROOT_*. That is the only moment this can happen - the same
// constraint that stops auth being switched on for an existing volume.
//
// The application then connects as this scoped user instead of root, so a
// compromised app credential cannot touch other databases, create users, or
// administer the server.
//
// Skipped silently when MONGO_APP_USER/PASSWORD are unset, which keeps the
// previous behaviour for anyone who has not opted in.
(function () {
  const user = process.env.MONGO_APP_USER || '';
  const password = process.env.MONGO_APP_PASSWORD || '';
  const dbName = process.env.MONGO_INITDB_DATABASE || 'tinymrp-v2';

  if (!user || !password) {
    print('[tinymrp] MONGO_APP_USER/PASSWORD not set; skipping scoped user.');
    return;
  }

  const appDb = db.getSiblingDB(dbName);
  const existing = appDb.getUser(user);
  if (existing) {
    print('[tinymrp] scoped user already exists: ' + user);
    return;
  }

  // readWrite on ONE database. Deliberately not dbOwner: the application never
  // creates users or indexes outside its own migrations.
  appDb.createUser({
    user: user,
    pwd: password,
    roles: [{ role: 'readWrite', db: dbName }],
  });
  print('[tinymrp] created scoped application user ' + user + ' on ' + dbName);
})();
