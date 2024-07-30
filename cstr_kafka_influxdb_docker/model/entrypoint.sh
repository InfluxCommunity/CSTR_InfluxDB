#!/bin/sh

# Start the cstr_model script first
faust -A cstr_model worker -l info &

# Wait for a few seconds to ensure cstr_model is up and running
sleep 10

# Start the pid_controller script
faust -A pid_controller worker -l info
