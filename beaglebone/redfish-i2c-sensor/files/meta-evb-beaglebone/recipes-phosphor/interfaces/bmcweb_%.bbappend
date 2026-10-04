# Show the BMC's event log (xyz.openbmc_project.Logging entries) in Redfish at
# /redfish/v1/Systems/system/LogServices/EventLog/Entries and on the web UI's
# "Event logs" page. Off by default in OpenBMC.
PACKAGECONFIG:append = " redfish-dbus-log"
