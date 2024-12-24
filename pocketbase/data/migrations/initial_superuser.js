// https://pocketbase.io/docs/js-migrations/#creating-initial-superuser
// pb_migrations/1687801090_initial_superuser.js

migrate((app) => {
  let superusers = app.findCollectionByNameOrId("_superusers")

  let record = new Record(superusers)

  // note: the values can be eventually loaded via $os.getenv(key)
  // or from a special local config file
  record.set("email", "umbrel@umbrel.local")
  record.set("password", "umbrel-pocketbase")

  app.save(record)
}, (app) => { // optional revert operation
  try {
      let record = app.findAuthRecordByEmail("_superusers", "umbrel@umbrel.local")
      app.delete(record)
  } catch {
      // silent errors (probably already deleted)
  }
})
