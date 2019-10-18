using System;

namespace IIS.Models.Tickets
{
    public class Ticket
    {
        public long Id { get; set; }
        public Airport FromAirport { get; set; }
        public Airport ToAirport { get; set; }
        public DateTime Date { get; set; }
        public decimal Price { get; set; }
        public Company Company { get; set; }
        public Category Category { get; set; }

        public Ticket(long id, Airport fromAirport, Airport toAirport, DateTime date, decimal price, Company company, Category category)
        {
            Id = id;
            FromAirport = fromAirport;
            ToAirport = toAirport;
            Date = date;
            Price = price;
            Company = company;
            Category = category;
        }

    }
}