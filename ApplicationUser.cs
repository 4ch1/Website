using System;
using System.IO.MemoryMappedFiles;
using System.Threading.Tasks;
using IIS.Models.Tickets;
using IIS.Queries;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;

namespace NewMvcProject.Models
{
    public class ApplicationUser
    {
        public ApplicationUser(string email, string password, string firstName, string lastName, string address, RightsEnum rights = RightsEnum.USER)
        {
            Email = email;
            Password = password;
            FirstName = firstName;
            LastName = lastName;
            Address = address;
            Rights = rights;
        }

        public ApplicationUser()
        {
            Email = default(string);
            Password = default(string);
            FirstName = default(string);
            LastName = default(string);
            Address = default(string);
        }

        public string Email { get; set; }
        public string Password { get; set; }
        public string FirstName { get; set; }
        public string LastName { get; set; }
        public string Address { get; set; }
        public RightsEnum Rights { get; set; }

        public bool IsDummy => string.IsNullOrEmpty(Email);

        public enum RightsEnum
        {
            USER,
            MODERATOR,
            ADMIN
        }

        public async Task<Company> GetCompany()
        {
            return await EmployeesQueries.GetByEmail(Email);
        }
    }
}