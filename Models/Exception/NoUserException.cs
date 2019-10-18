using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace IIS.Models.Exception
{
    public class NoUserException:System.Exception
    {
        public NoUserException(string email) : base($"No user with email {email}")
        {

        }
    }
}
