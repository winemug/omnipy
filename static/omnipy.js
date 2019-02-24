   function autorun()
   {
    new Vue({
        el: "#app",
        data: {
            result: {},
            formatted: {},
            request: {}
        },
        methods: {
            set_password: function() {
                var pwd = this.request.password;
            },
            status: function() {
              var url = "/pdm/status"
              this.api_call(url)
            },
            set_temp_basal: function() {
              var url = "/pdm/settempbasal"
              url += "?amount=" + this.request.temp_basal_rate
              url += "&hours=" + this.request.temp_basal_duration
              this.api_call(url)
            },
            start_bolus: function() {
              var url = "/pdm/bolus"
              url += "?amount=" + this.request.bolus_amount
              this.api_call(url)
            },
            stop_bolus: function() {
              var url = "/pdm/cancelbolus"
              url += "?amount=" + this.request.temp_basal_rate
              url += "&hours=" + this.request.temp_basal_duration
              this.api_call(url)
            },
            api_call: function(url)
            {
              var req = new XMLHttpRequest();
              req.onreadystatechange = function(req) {
              if (req.readyState == XMLHttpRequest.DONE && req.status == 200) {
                  this.result = JSON.parse(req.responseText).result;
                  this.format_results();
              }
              }.bind(this, req);
              req.open("GET", url, true);
              req.send();
            },
            format_results: function ()
            {
              var date = new Date(this.result.lastUpdated * 1000);

              var month = new Array();
              month[0] = "January";
              month[1] = "February";
              month[2] = "March";
              month[3] = "April";
              month[4] = "May";
              month[5] = "June";
              month[6] = "July";
              month[7] = "August";
              month[8] = "September";
              month[9] = "October";
              month[10] = "November";
              month[11] = "December";
              this.formatted.last_updated = month[date.getMonth()] + " " + date.getDay().toString() + ", " +
                date.toTimeString().slice(0, 8)

              var minutes = this.result.minutes_since_activation;
              var days = Math.floor(minutes / 1440)
              minutes -= days*1440;
              var hours = Math.floor(minutes / 60)
              minutes -= hours*60

              this.formatted.time_active = days.toString() + "d " + hours.toString() + "h " + minutes.toString() +"m";

              switch(this.result.bolusState)
              {
                case 0: this.formatted.bolus_state = "Not running"; break;
                case 1: this.formatted.bolus_state = "Extended bolus active"; break;
                case 2: this.formatted.bolus_state = "Immediate bolus active"; break;
              }

              switch(this.result.basalState)
              {
                case 0: this.formatted.basal_state = "Not running"; break;
                case 1: this.formatted.basal_state = "Temp. basal active"; break;
                case 2: this.formatted.basal_state = "Normal basal active"; break;
              }

              this.request = {}
            },
        }
        })
   }

      if (document.addEventListener) document.addEventListener("DOMContentLoaded", autorun, false);
   else if (document.attachEvent) document.attachEvent("onreadystatechange", autorun);
   else window.onload = autorun;
