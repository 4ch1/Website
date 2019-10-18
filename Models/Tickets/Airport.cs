using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace IIS.Models.Tickets
{
    public class Airport
    {
        public string FullName { get; set; }
        public string ShortName { get; set; }
        public string Location { get; set; }

        public Airport(string fullName, string shortName, string location)
        {
            FullName = fullName;
            ShortName = shortName;
            Location = location;
        }
    }
}
