namespace IIS.Models.Tickets
{
    public class Company
    {
        public string FullName { get; set; }
        public string ShortName { get; set; }

        public Company(string fullName, string shortName)
        {
            FullName = fullName;
            ShortName = shortName;
        }
    }
}